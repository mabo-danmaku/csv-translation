import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import deepl
import logging
import os
import time
import csv
import json
import threading
import chardet
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Tuple

# Setup logging with custom handler to capture logs for GUI
class GUILogHandler(logging.Handler):
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        # Schedule append in the GUI thread
        self.text_widget.after(0, append)

# 起動前に.envファイルの読み込みを試行
load_dotenv()

class DeepLTranslator:
    def __init__(self, log_widget=None):
        self.auth_key = self.get_api_key()
        self.translator = deepl.Translator(self.auth_key)
        self.supported_languages = self.load_supported_languages()
        self.log_widget = log_widget
        self.progress_callback = None
        self.stop_translation = False
        # 一般的なエンコーディングリストを追加
        self.common_encodings = [
            'auto', 'utf-8', 'utf-8-sig', 'shift-jis', 'cp932', 'euc-jp', 
            'iso-2022-jp', 'latin-1', 'ascii', 'utf-16', 'utf-16-le', 'utf-16-be',
            'cp1252', 'gb2312', 'big5', 'euc-kr'
        ]

    @staticmethod
    def get_api_key() -> str:
        api_key = os.environ.get("DEEPL_AUTH_KEY")
        if not api_key:
            raise ValueError("DeepL APIキーが設定されていません。.envファイルを確認してください。")
        return api_key

    @staticmethod
    def load_supported_languages() -> List[dict]:
        languages_file = "languages.json"
        if not os.path.exists(languages_file):
            raise FileNotFoundError(f"言語ファイル '{languages_file}' が見つかりません。")
            
        try:
            with open(languages_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise ValueError(f"言語ファイルの読み込みエラー: {str(e)}")

    def get_output_path(self, input_path: str) -> str:
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        return str(Path(input_path).parent / f"output_{timestamp}.csv")

    def detect_encoding(self, file_path: str) -> Tuple[str, float]:
        """ファイルのエンコーディングを検出する"""
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding'], result['confidence']
    
    def try_read_csv(self, file_path: str, encoding: str = None) -> Tuple[pd.DataFrame, str]:
        """指定されたエンコーディングでCSVファイルを読み込む、失敗したら自動検出を試みる"""
        if encoding and encoding != "auto":
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                logging.info(f"エンコーディング '{encoding}' でファイルを読み込みました。")
                return df, encoding
            except UnicodeDecodeError:
                logging.warning(f"指定されたエンコーディング '{encoding}' でファイルを読み込めませんでした。自動検出を試みます。")
                
        # 自動検出を試みる
        detected_encoding, confidence = self.detect_encoding(file_path)
        logging.info(f"エンコーディングを検出しました: {detected_encoding} (信頼度: {confidence:.2f})")
        
        # 検出したエンコーディングで読み込みを試みる
        try:
            df = pd.read_csv(file_path, encoding=detected_encoding)
            return df, detected_encoding
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            logging.warning(f"検出したエンコーディングでも読み込めませんでした: {str(e)}")
            
            # 一般的なエンコーディングでの読み込みを試みる
            for enc in self.common_encodings:
                if enc != "auto" and enc != detected_encoding:  # "auto"と既に試したエンコーディングはスキップ
                    try:
                        df = pd.read_csv(file_path, encoding=enc)
                        logging.info(f"エンコーディング '{enc}' で正常に読み込みました。")
                        return df, enc
                    except (UnicodeDecodeError, pd.errors.ParserError):
                        continue
                        
            # すべて失敗した場合
            raise ValueError(f"ファイル '{file_path}' を読み込めるエンコーディングが見つかりませんでした。")

    def translate_csv_column(self, input_file: str, column_name: Optional[str] = None, 
                             column_index: Optional[int] = None, target_lang: str = "JA", 
                             has_header: bool = True, encoding: str = 'utf-8', log_interval: int = 10):
        output_file = self.get_output_path(input_file)
        self.stop_translation = False

        try:
            # エンコーディングの自動検出または検証
            logging.info(f"ファイル '{input_file}' を読み込んでいます...")
            df, used_encoding = self.try_read_csv(input_file, encoding)
            logging.info(f"エンコーディング '{used_encoding}' でファイルを読み込みました。")
            
            # ヘッダーの処理
            if not has_header:
                df = pd.read_csv(input_file, encoding=used_encoding, header=None)
                df.columns = [f"Column_{i}" for i in range(len(df.columns))]

            target_column = self.determine_column(df, column_name, column_index)
            logging.info(f"'{target_column}' 列を{target_lang}に翻訳します...")

            translated_texts = []
            total = len(df)

            for i, text in enumerate(df[target_column], 1):
                if self.stop_translation:
                    logging.info("翻訳が中断されました。")
                    return False

                translated_texts.append(self.translate_text(text, target_lang))

                if i % log_interval == 0 or i == total:
                    progress = i / total
                    logging.info(f"進捗: {i}/{total} ({progress*100:.1f}%)")
                    if self.progress_callback:
                        self.progress_callback(progress)

            df[target_column] = translated_texts
            df.to_csv(output_file, index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)

            logging.info(f"翻訳が完了し、結果を '{output_file}' に保存しました。")
            return output_file
        except Exception as e:
            logging.error(f"エラーが発生しました: {str(e)}")
            raise

    def determine_column(self, df: pd.DataFrame, column_name: Optional[str], column_index: Optional[int]) -> str:
        if column_name and column_name in df.columns:
            return column_name
        elif column_index is not None and 0 <= column_index < len(df.columns):
            return df.columns[column_index]
        else:
            raise ValueError("指定された列が見つかりません。")

    def translate_text(self, text: str, target_lang: str) -> str:
        if pd.isna(text) or not str(text).strip():
            return ""
        try:
            return self.translator.translate_text(str(text), target_lang=target_lang).text
        except deepl.DeepLException as e:
            logging.warning(f"DeepLエラー: {str(e)}")
            return text

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stop(self):
        self.stop_translation = True


class DeepLTranslatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepL CSV翻訳ツール")
        self.root.geometry("700x650")  # エンコーディング設定の追加に合わせてウィンドウサイズを調整
        self.root.resizable(True, True)
        
        # 初期化
        self.translator = None
        self.translation_thread = None
        self.log_text = None  # 先にNoneに初期化
        
        # 必要なファイルの確認
        try:
            self.check_required_files()
            self.create_widgets()
            self.setup_logging()
            
            # アプリケーション開始メッセージ
            logging.info("アプリケーションが起動しました。")
        except Exception as e:
            self.show_startup_error(str(e))
            return
    
    def check_required_files(self):
        """必要なファイルの存在を確認"""
        env_file = ".env"
        languages_file = "languages.json"
        
        missing_files = []
        
        # カレントディレクトリを表示（デバッグ用）
        current_dir = os.getcwd()
        print(f"カレントディレクトリ: {current_dir}")
        
        # ファイルパスの絶対パスを取得（デバッグ用）
        env_path = os.path.abspath(env_file)
        lang_path = os.path.abspath(languages_file)
        print(f".envファイルパス: {env_path}")
        print(f"languages.jsonファイルパス: {lang_path}")
        
        if not os.path.isfile(env_file):
            missing_files.append(f".envファイル（DeepL APIキーを設定してください）")
        else:
            # APIキーが設定されているか確認
            api_key = os.environ.get("DEEPL_AUTH_KEY")
            if not api_key:
                missing_files.append(f".envファイル内のDEEPL_AUTH_KEYが設定されていません")
        
        if not os.path.isfile(languages_file):
            missing_files.append(f"languages.jsonファイル（対応言語定義ファイル）")
            
        if missing_files:
            raise FileNotFoundError(f"以下の必須ファイルが見つかりません:\n" + "\n".join(missing_files))
    
    def show_startup_error(self, error_message):
        """起動時エラーを表示してアプリケーションを終了"""
        messagebox.showerror("起動エラー", f"アプリケーションを起動できません:\n\n{error_message}")
        self.root.after(100, self.root.destroy())  # 少し遅延して終了
        
    def setup_logging(self):
        # ロガー設定前にウィジェットが初期化されていることを確認
        if self.log_text is None:
            return
            
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 既存のハンドラをクリア
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # コンソールハンドラ
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # GUIハンドラ
        gui_handler = GUILogHandler(self.log_text)
        gui_handler.setLevel(logging.INFO)
        gui_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        gui_handler.setFormatter(gui_formatter)
        root_logger.addHandler(gui_handler)
    
    def create_widgets(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ファイル選択セクション
        file_frame = ttk.LabelFrame(main_frame, text="CSVファイル選択", padding="5")
        file_frame.pack(fill=tk.X, pady=5)
        
        self.file_path = tk.StringVar()
        ttk.Label(file_frame, text="ファイルパス:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.file_path, width=50).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(file_frame, text="参照...", command=self.browse_file).grid(row=0, column=2, padx=5, pady=5)
        
        # ヘッダーのチェックボックス
        self.has_header = tk.BooleanVar(value=True)
        ttk.Checkbutton(file_frame, text="ヘッダー行あり", variable=self.has_header).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        # エンコーディング選択セクション（新規追加）
        encoding_frame = ttk.LabelFrame(main_frame, text="ファイルエンコーディング", padding="5")
        encoding_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(encoding_frame, text="エンコーディング:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.encoding = ttk.Combobox(encoding_frame, width=20)
        self.encoding.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # 初期化用のトランスレータインスタンスを一時的に作成
        temp_translator = DeepLTranslator()
        self.encoding['values'] = temp_translator.common_encodings
        self.encoding.current(0)  # 'auto'を初期選択
        
        ttk.Label(encoding_frame, text="※「auto」を選択すると自動検出を試みます").grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # 列選択セクション
        column_frame = ttk.LabelFrame(main_frame, text="翻訳する列の選択", padding="5")
        column_frame.pack(fill=tk.X, pady=5)
        
        self.column_method = tk.StringVar(value="name")
        ttk.Radiobutton(column_frame, text="列名で指定", variable=self.column_method, value="name").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(column_frame, text="インデックスで指定", variable=self.column_method, value="index").grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.column_value = tk.StringVar()
        ttk.Label(column_frame, text="列名/インデックス:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(column_frame, textvariable=self.column_value, width=20).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # 言語選択セクション
        lang_frame = ttk.LabelFrame(main_frame, text="翻訳設定", padding="5")
        lang_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(lang_frame, text="翻訳先言語:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_lang = ttk.Combobox(lang_frame, width=30)
        self.target_lang.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # ログ間隔設定
        ttk.Label(lang_frame, text="ログ間隔 (行数):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.log_interval = tk.StringVar(value="10")
        ttk.Entry(lang_frame, textvariable=self.log_interval, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 実行ボタンセクション
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="翻訳開始", command=self.start_translation)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="中止", command=self.stop_translation, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 検出エンコーディング表示ボタン
        self.detect_encoding_button = ttk.Button(button_frame, text="ファイルエンコーディング検出", command=self.detect_file_encoding)
        self.detect_encoding_button.pack(side=tk.LEFT, padx=5)
        
        # プログレスバー
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(progress_frame, text="進捗状況:").pack(side=tk.LEFT, padx=5)
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # ログ表示エリア
        log_frame = ttk.LabelFrame(main_frame, text="ログ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state='disabled')
        
        # 言語リストの読み込み
        self.load_languages()
        
        # カラム調整
        main_frame.columnconfigure(0, weight=1)
        file_frame.columnconfigure(1, weight=1)
        column_frame.columnconfigure(1, weight=1)
        lang_frame.columnconfigure(1, weight=1)
    
    def load_languages(self):
        try:
            # 言語ファイルの読み込みを試行
            with open("languages.json", encoding="utf-8") as f:
                languages = json.load(f)
            
            if languages:
                language_options = [f"{lang['code']} - {lang['name']}" for lang in languages]
                self.target_lang['values'] = language_options
                
                # 日本語を初期選択
                try:
                    self.target_lang.current(languages.index(next(lang for lang in languages if lang['code'] == 'JA')))
                except (StopIteration, ValueError):
                    # 日本語がなければ最初の言語を選択
                    self.target_lang.current(0)
            else:
                messagebox.showwarning("警告", "言語リストが空です。翻訳に影響する可能性があります。")
        except Exception as e:
            messagebox.showwarning("警告", f"言語リスト読み込みエラー: {str(e)}")
    
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="CSVファイルを選択",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.file_path.set(filename)
    
    def detect_file_encoding(self):
        """選択されたファイルのエンコーディングを検出してユーザーに通知"""
        if not self.file_path.get():
            messagebox.showerror("エラー", "CSVファイルを選択してください。")
            return
            
        try:
            # 一時的なトランスレータインスタンスを作成
            temp_translator = DeepLTranslator()
            detected_encoding, confidence = temp_translator.detect_encoding(self.file_path.get())
            
            # エンコーディング情報をユーザーに表示
            messagebox.showinfo(
                "エンコーディング検出結果", 
                f"検出されたエンコーディング: {detected_encoding}\n信頼度: {confidence:.2f}\n\n"
                f"※このエンコーディングを使用する場合は、ドロップダウンから選択してください。\n"
                f"※検出された結果がドロップダウンにない場合は「auto」を選択してください。"
            )
            
            # 検出されたエンコーディングがドロップダウンリストにある場合、自動選択
            encoding_values = self.encoding['values']
            if detected_encoding in encoding_values:
                self.encoding.set(detected_encoding)
            
        except Exception as e:
            messagebox.showerror("エラー", f"エンコーディング検出中にエラーが発生しました: {str(e)}")
    
    def update_progress(self, value):
        self.progress_bar['value'] = value * 100
    
    def enable_controls(self, enabled=True):
        state = tk.NORMAL if enabled else tk.DISABLED
        disabled_state = tk.DISABLED if enabled else tk.NORMAL
        
        self.start_button['state'] = state
        self.stop_button['state'] = disabled_state
        self.detect_encoding_button['state'] = state
    
    def start_translation(self):
        if not self.file_path.get():
            messagebox.showerror("エラー", "CSVファイルを選択してください。")
            return
        
        if not self.column_value.get():
            messagebox.showerror("エラー", "翻訳する列を指定してください。")
            return
        
        try:
            # ログインターバルの検証
            log_interval = int(self.log_interval.get())
            if log_interval <= 0:
                messagebox.showerror("エラー", "ログ間隔は正の整数を指定してください。")
                return
        except ValueError:
            messagebox.showerror("エラー", "ログ間隔は整数を入力してください。")
            return
        
        # UI要素の状態変更
        self.enable_controls(False)
        self.progress_bar['value'] = 0
        
        # 翻訳オブジェクトの初期化
        try:
            self.translator = DeepLTranslator(self.log_text)
            self.translator.set_progress_callback(self.update_progress)
        except Exception as e:
            messagebox.showerror("エラー", f"翻訳機能の初期化に失敗しました: {str(e)}")
            self.enable_controls(True)
            return
        
        # 翻訳パラメータの準備
        target_lang_code = self.target_lang.get().split(' - ')[0].strip()
        column_name = None
        column_index = None
        
        if self.column_method.get() == "name":
            column_name = self.column_value.get()
        else:
            try:
                column_index = int(self.column_value.get())
            except ValueError:
                messagebox.showerror("エラー", "列インデックスは整数を入力してください。")
                self.enable_controls(True)
                return
        
        # エンコーディングの取得
        encoding = self.encoding.get()
        
        # 翻訳処理を別スレッドで実行
        self.translation_thread = threading.Thread(
            target=self.run_translation,
            args=(
                self.file_path.get(),
                column_name,
                column_index,
                target_lang_code,
                self.has_header.get(),
                encoding,
                log_interval
            )
        )
        self.translation_thread.daemon = True
        self.translation_thread.start()
    
    def run_translation(self, input_file, column_name, column_index, target_lang, has_header, encoding, log_interval):
        try:
            output_file = self.translator.translate_csv_column(
                input_file, column_name, column_index, target_lang, 
                has_header, encoding, log_interval
            )
            
            if output_file:
                self.root.after(0, lambda: messagebox.showinfo("完了", f"翻訳が完了しました。\n出力ファイル: {output_file}"))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(str(e)))
        finally:
            self.root.after(0, lambda: self.enable_controls(True))
    
    def stop_translation(self):
        if self.translator:
            self.translator.stop()
            logging.info("翻訳を中止しています...")
    
    def show_error(self, error_message):
        error_window = tk.Toplevel(self.root)
        error_window.title("エラー")
        error_window.geometry("500x300")
        
        error_text = scrolledtext.ScrolledText(error_window, wrap=tk.WORD)
        error_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        error_text.insert(tk.END, f"エラーが発生しました:\n\n{error_message}")
        error_text.configure(state='disabled')
        
        ttk.Button(error_window, text="閉じる", command=error_window.destroy).pack(pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = DeepLTranslatorGUI(root)
    root.mainloop()
