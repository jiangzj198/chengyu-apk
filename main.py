# -*- coding: utf-8 -*-
"""
智能成语学习助手（双端适配版 - 电脑+手机通用）
功能：
1. 每轮随机10道成语填空题，每题10分，满分100分
2. 答完自动显示分数统计，一键开启下一轮
3. 支持上一题/下一题、成语详解、成语查找
4. 成语详情自动朗读：成语+拼音+释义+例句
5. 答错成语自动收集到错题本，方便复习
6. 答对/答错音效反馈，+10分即时弹窗提醒
"""

import os
import sys
import time
import random
import json
import math
import array
import threading

from kivy.utils import platform
from kivy.config import Config

# ===========================================================================
# 平台差异化配置
# ===========================================================================
IS_MOBILE = platform in ("android", "ios")

if not IS_MOBILE:
    Config.set('graphics', 'width', '480')
    Config.set('graphics', 'height', '640')
    Config.set('input', 'mouse', 'mouse,disable_multitouch')
else:
    Config.set('graphics', 'fullscreen', 'auto')
    Config.set('kivy', 'window_icon', '')
    if platform == "android":
        try:
            from android import loadingscreen
            loadingscreen.hide()
        except Exception:
            pass
        # 本程序只读写应用私有目录（错题本、音效缓存），
        # 现代安卓无需外部存储权限，这里不再申请，避免多余授权弹窗。

from kivy.core.text import LabelBase
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, NumericProperty
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.core.audio import SoundLoader

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.scrollview import MDScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
    MDDialogContentContainer,
)


# ===========================================================================
# 自适应尺寸工具
# ===========================================================================
def get_scale_factor():
    if IS_MOBILE:
        screen_width = min(Window.width, Window.height)
        scale = screen_width / dp(480)
        return max(0.85, min(1.3, scale))
    return 1.0


SCALE = get_scale_factor()

def sdp(value):
    return dp(value * SCALE)

def ssp(value):
    return sp(value * SCALE)


# ===========================================================================
# 资源路径工具（Windows / 安卓 通用）
# ===========================================================================
def get_resource_path(relative_path):
    """只读资源（题库、字体等）的绝对路径。

    - 源码直接运行：脚本所在目录
    - Windows 打包（PyInstaller）：解包目录 sys._MEIPASS
    - 安卓打包（python-for-android）：脚本所在的应用私有目录
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_writable_path(filename):
    """可写数据文件（错题本、缓存的音效）的绝对路径。

    - 安卓：App.user_data_dir（应用私有可写目录，无需存储权限）
    - Windows 打包后：exe 所在目录（不能写只读的 _MEIPASS）
    - 源码直接运行：脚本所在目录
    """
    base_dir = None
    if IS_MOBILE:
        try:
            from kivy.app import App
            app = App.get_running_app()
            if app is not None:
                base_dir = app.user_data_dir
        except Exception:
            base_dir = None
    if not base_dir:
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base_dir, filename)


# ===========================================================================
# 中文字体注册
# ===========================================================================
_FONT_CANDIDATES = [
    ("app_zh",
     get_resource_path(os.path.join("fonts", "zh_regular.ttf")),
     get_resource_path(os.path.join("fonts", "zh_bold.ttf"))),
    ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"),
    ("SimHei", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simhei.ttf"),
    ("PingFang", "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
    ("STHeiti", "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"),
    ("NotoSansCJK", "/system/fonts/NotoSansCJK-Regular.ttc", "/system/fonts/NotoSansCJK-Bold.ttc"),
    ("DroidSansFallback", "/system/fonts/DroidSansFallback.ttf", "/system/fonts/DroidSansFallback.ttf"),
    ("WenQuanYi", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
     "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ("NotoSansCJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
]

ZH_FONT_NAME = "ChineseFont"

def register_chinese_font():
    for name, regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            bold_path = bold if os.path.exists(bold) else regular
            try:
                LabelBase.register(name=ZH_FONT_NAME, fn_regular=regular, fn_bold=bold_path)
                print(f"[字体] 已加载中文字体: {regular}")
                return ZH_FONT_NAME
            except Exception as exc:
                print(f"[字体] 注册失败 {regular}: {exc}")
                continue
    print("[字体] 未找到可用的中文字体！")
    return "Roboto"

register_chinese_font()

def apply_chinese_font_to_theme(theme_cls):
    styles = theme_cls.font_styles
    for style_name, roles in styles.items():
        if style_name == "Icon":
            continue
        for role_name in roles:
            roles[role_name]["font-name"] = ZH_FONT_NAME


# ===========================================================================
# 音效模块：程序启动时自动生成答对/答错短音效wav文件
# 不依赖外部音频文件，程序自带生成
# ===========================================================================
def _generate_sound_wav(filepath, frequency, duration=0.15, volume=0.4, sample_rate=22050):
    """生成简单正弦波音效wav文件"""
    try:
        import wave
        num_samples = int(duration * sample_rate)
        buf = array.array('h')
        amp = int(32767 * volume)
        for i in range(num_samples):
            # 带一点点衰减，声音更自然
            t = i / sample_rate
            env = max(0.0, 1.0 - t / duration * 0.5)
            sample = int(amp * env * math.sin(2 * math.pi * frequency * t))
            buf.append(sample)
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(buf.tobytes())
        return True
    except Exception as e:
        print(f"[音效] 生成失败: {e}")
        return False


SOUND_CORRECT = None
SOUND_WRONG = None

def init_sounds():
    """初始化音效：在程序目录生成两个临时wav并加载"""
    global SOUND_CORRECT, SOUND_WRONG
    correct_path = get_writable_path("_sound_correct.wav")
    wrong_path = get_writable_path("_sound_wrong.wav")

    # 文件不存在则生成
    if not os.path.exists(correct_path):
        _generate_sound_wav(correct_path, frequency=880, duration=0.2, volume=0.35)
    if not os.path.exists(wrong_path):
        _generate_sound_wav(wrong_path, frequency=220, duration=0.3, volume=0.35)

    try:
        SOUND_CORRECT = SoundLoader.load(correct_path)
        SOUND_WRONG = SoundLoader.load(wrong_path)
        print("[音效] 已加载答题反馈音效")
    except Exception as e:
        print(f"[音效] 加载失败: {e}")
        SOUND_CORRECT = None
        SOUND_WRONG = None


def play_correct_sound():
    try:
        if SOUND_CORRECT:
            SOUND_CORRECT.seek(0)
            SOUND_CORRECT.play()
    except Exception:
        pass


def play_wrong_sound():
    try:
        if SOUND_WRONG:
            SOUND_WRONG.seek(0)
            SOUND_WRONG.play()
    except Exception:
        pass


# ===========================================================================
# 语音播报模块（双端适配）
# ===========================================================================
class SpeechEngine:
    """统一语音播报接口"""

    def __init__(self):
        self._android_tts = None
        self._android_listener = None
        self._android_ready = False
        self._desktop_driver = None
        self._desktop_voice_id = None
        self._lock = threading.Lock()
        self._ready = False
        self._mode = None
        self._init()

    def _init(self):
        try:
            import logging
            logging.getLogger("comtypes").setLevel(logging.ERROR)
        except Exception:
            pass
        try:
            import os as _os
            _os.environ.setdefault("COMTYPES_DEBUG", "0")
        except Exception:
            pass

        if IS_MOBILE and platform == "android":
            self._init_android()
        else:
            self._init_desktop_probe()

    def _init_android(self):
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
            Locale = autoclass("java.util.Locale")
            activity = PythonActivity.mActivity

            holder = self

            class _OnInitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                @java_method("(I)V")
                def onInit(self, status):
                    # status == 0 表示 TTS 引擎初始化成功
                    try:
                        if status != 0:
                            return
                        try:
                            holder._android_tts.setLanguage(Locale.CHINA)
                        except Exception:
                            try:
                                holder._android_tts.setLanguage(Locale.getDefault())
                            except Exception:
                                pass
                        try:
                            holder._android_tts.setSpeechRate(0.9)
                        except Exception:
                            pass
                        holder._android_ready = True
                    except Exception:
                        pass

            self._android_listener = _OnInitListener()
            try:
                self._android_tts = TextToSpeech(activity, self._android_listener)
            except Exception:
                # 个别机型不接受 Python 回调，退回无回调方式
                self._android_tts = TextToSpeech(activity, None)
                self._android_ready = True
            self._mode = "android"
            self._ready = True
            print("[语音] 已启用安卓系统语音引擎")
        except Exception as exc:
            print(f"[语音] 安卓不可用: {exc}")

    def _init_desktop_probe(self):
        try:
            import pyttsx3
            _tmp = pyttsx3.init()
            self._desktop_driver = getattr(_tmp, "_driverName", None)
            try:
                for v in _tmp.getProperty("voices"):
                    meta = (" ".join(getattr(v, "languages", []) or [])
                            + " " + str(getattr(v, "id", ""))
                            + " " + str(getattr(v, "name", ""))).lower()
                    if any(k in meta for k in ("chinese", "zh", "中文", "china")):
                        self._desktop_voice_id = v.id
                        break
            except Exception:
                pass
            try:
                _tmp.stop()
            except Exception:
                pass
            del _tmp
            self._mode = "desktop"
            self._ready = True
            print("[语音] 电脑端语音可用")
        except Exception as exc:
            print(f"[语音] 电脑端语音不可用（pip install pyttsx3）: {exc}")

    @property
    def available(self):
        return self._ready

    def speak(self, text):
        """单次朗读（打断当前朗读）"""
        self.stop()
        if not text or not self._ready:
            return
        text = str(text).strip()
        if not text:
            return
        threading.Thread(target=self._speak_once, args=(text,), daemon=True).start()

    def stop(self):
        try:
            if self._mode == "android" and self._android_tts is not None:
                self._android_tts.stop()
        except Exception:
            pass

    def _speak_once(self, text):
        """单次朗读的内部实现"""
        with self._lock:
            try:
                if self._mode == "android":
                    # 等引擎初始化完成再朗读，最多等约 1.5 秒
                    waited = 0.0
                    while not self._android_ready and waited < 1.5:
                        time.sleep(0.1)
                        waited += 0.1
                    self._android_tts.speak(text, 1, None, None)
                elif self._mode == "desktop":
                    import pyttsx3
                    try:
                        import comtypes
                        comtypes.CoInitialize()
                    except Exception:
                        pass
                    engine = pyttsx3.init(driverName=self._desktop_driver)
                    try:
                        engine.setProperty("rate", 150)
                        engine.setProperty("volume", 1.0)
                        if self._desktop_voice_id:
                            try:
                                engine.setProperty("voice", self._desktop_voice_id)
                            except Exception:
                                pass
                        engine.stop()
                        engine.say(text)
                        engine.runAndWait()
                    finally:
                        try:
                            engine.stop()
                        except Exception:
                            pass
                        try:
                            del engine
                        except Exception:
                            pass
            except Exception as exc:
                print(f"[语音] 播报失败: {exc}")


SPEECH = SpeechEngine()


def _build_speak_text(word, pinyin="", explanation="", example="", extra=""):
    """组装朗读文本：成语 + 拼音 + 释义 + 例句（例句也读出来方便记忆）"""
    parts = []
    if word:
        parts.append(str(word).strip())
    if pinyin:
        py = str(pinyin).replace(" ", "").strip()
        if py:
            parts.append(py)
    if explanation:
        text = str(explanation).strip()
        for ch in "《》〈〉()（）":
            text = text.replace(ch, "")
        parts.append(text)
    if example and str(example).strip() and str(example).strip() != "暂无":
        ex_text = str(example).strip()
        for ch in "《》〈〉()（）":
            ex_text = ex_text.replace(ch, "")
        parts.append("例句：" + ex_text)
    if extra:
        parts.append(str(extra).strip())
    return "，".join(p for p in parts if p)


# ===========================================================================
# 错题本模块：自动保存答错的成语，支持复习
# ===========================================================================
def _wrong_book_path():
    """错题本文件路径（安卓写入应用私有目录，桌面写入程序目录）"""
    return get_writable_path("wrong_idioms.json")


def load_wrong_book():
    """加载错题本，返回 dict: {word: 错误次数}"""
    path = _wrong_book_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_wrong_book(wrong_dict):
    """保存错题本"""
    try:
        with open(_wrong_book_path(), "w", encoding="utf-8") as f:
            json.dump(wrong_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[错题本] 保存失败: {e}")


def add_to_wrong_book(idiom):
    """把答错的成语加入错题本"""
    word = idiom.get("word", "")
    if not word:
        return
    wrong_dict = load_wrong_book()
    wrong_dict[word] = wrong_dict.get(word, 0) + 1
    save_wrong_book(wrong_dict)


# ===========================================================================
# 成语库加载
# ===========================================================================
IDIOM_JSON_PATH = get_resource_path("idiom.json")

DEFAULT_DATABASE = [
    {"word": "一心一意", "pinyin": "yī xīn yī yì", "explanation": "只有一个心眼儿，没有别的考虑。",
     "derivation": "《三国志·魏志·杜恕传》", "example": "他一心一意地学习，成绩进步很快。"},
    {"word": "意气风发", "pinyin": "yì qì fēng fā", "explanation": "形容精神振奋，气概豪迈。",
     "derivation": "三国·魏·曹植《魏德论》", "example": "同学们意气风发地走进校园。"},
    {"word": "发扬光大", "pinyin": "fā yáng guāng dà", "explanation": "使好的作风、传统等得到发展和提高。",
     "derivation": "《周易·坤》", "example": "我们要把优良传统发扬光大。"},
    {"word": "山穷水尽", "pinyin": "shān qióng shuǐ jìn", "explanation": "山和水都到了尽头。比喻无路可走陷入绝境。",
     "derivation": "宋·陆游《游山西村》", "example": "他已经到了山穷水尽的地步。"},
    {"word": "柳暗花明", "pinyin": "liǔ àn huā míng",
     "explanation": "垂柳浓密，鲜花夺目。也比喻在困难中遇到转机。", "derivation": "唐·王维《早朝》",
     "example": "就在大家着急的时候，事情突然柳暗花明了。"},
    {"word": "明察秋毫", "pinyin": "míng chá qiū háo",
     "explanation": "原形容人目光敏锐，后多形容人能洞察事理。", "derivation": "《孟子·梁惠王上》",
     "example": "包青天明察秋毫，断案如神。"},
    {"word": "毫不在意", "pinyin": "háo bù zài yì", "explanation": "丝毫不在乎或不介意。",
     "derivation": "清·石玉昆《三侠五义》", "example": "他对别人的议论毫不在意。"},
    {"word": "意味深长", "pinyin": "yì wèi shēn cháng", "explanation": "意思含蓄深远，耐人寻味。",
     "derivation": "宋·程颢《河南程氏遗书》", "example": "老师说的话意味深长。"},
    {"word": "长治久安", "pinyin": "cháng zhì jiǔ ān", "explanation": "形容国家长期安定、巩固。",
     "derivation": "《汉书·贾谊传》", "example": "百姓都希望国家长治久安。"},
    {"word": "安居乐业", "pinyin": "ān jū lè yè", "explanation": "指安定愉快地生活和劳动。", "derivation": "《老子》",
     "example": "人民安居乐业，国家才能繁荣。"},
    {"word": "业精于勤", "pinyin": "yè jīng yú qín", "explanation": "学业精深是由勤奋得来的。",
     "derivation": "唐·韩愈《进学解》", "example": "老师常说业精于勤，鼓励我们勤奋学习。"},
    {"word": "勤能补拙", "pinyin": "qín néng bǔ zhuō", "explanation": "勤奋能够弥补笨拙。",
     "derivation": "宋·邵雍《弄笔吟》", "example": "勤能补拙，只要努力就会进步。"},
    {"word": "水落石出", "pinyin": "shuǐ luò shí chū", "explanation": "比喻事情的真相完全显露出来。",
     "derivation": "宋·欧阳修《醉翁亭记》", "example": "经过调查，事情终于水落石出。"},
    {"word": "出口成章", "pinyin": "chū kǒu chéng zhāng", "explanation": "说出话来就成文章，形容文思敏捷。",
     "derivation": "《诗经·小雅·都人士》", "example": "他博学多才，出口成章。"},
    {"word": "徒劳无功", "pinyin": "tú láo wú gōng", "explanation": "白白付出劳动而没有成效。",
     "derivation": "《庄子·天运》", "example": "不讲究方法，只会徒劳无功。"},
    {"word": "功成名就", "pinyin": "gōng chéng míng jiù", "explanation": "功绩取得了，名声也有了。",
     "derivation": "《墨子·修身》", "example": "他努力多年，终于功成名就。"},
    {"word": "事倍功半", "pinyin": "shì bèi gōng bàn", "explanation": "指工作费力大，收效小。",
     "derivation": "《孟子·公孙丑上》", "example": "方法不对就会事倍功半。"},
    {"word": "半信半疑", "pinyin": "bàn xìn bàn yí", "explanation": "有点相信，又有点怀疑。",
     "derivation": "三国·魏·嵇康《答释难宅无吉凶摄生论》", "example": "他半信半疑地听着朋友的话。"},
    {"word": "猝不及防", "pinyin": "cù bù jí fáng", "explanation": "事情来得突然，来不及防备。",
     "derivation": "清·纪昀《阅微草堂笔记》", "example": "暴风雨来得猝不及防。"},
    {"word": "防微杜渐", "pinyin": "fáng wēi dù jiàn", "explanation": "比喻在坏事情萌芽时就加以制止。",
     "derivation": "《后汉书·丁鸿传》", "example": "坏习惯要及时改正，做到防微杜渐。"},
    {"word": "渐入佳境", "pinyin": "jiàn rù jiā jìng", "explanation": "比喻境况逐渐好转或兴趣渐浓。",
     "derivation": "《晋书·顾恺之传》", "example": "读到后面，这本书渐入佳境。"},
    {"word": "一丝不苟", "pinyin": "yī sī bù gǒu", "explanation": "形容做事认真细致，一点儿不马虎。",
     "derivation": "清·吴敬梓《儒林外史》", "example": "他做作业一丝不苟。"},
    {"word": "兴高采烈", "pinyin": "xìng gāo cǎi liè", "explanation": "形容兴致高，精神饱满。",
     "derivation": "南朝·梁·刘勰《文心雕龙》", "example": "同学们兴高采烈地去郊游。"},
]


def load_idiom_database():
    if not os.path.exists(IDIOM_JSON_PATH):
        try:
            with open(IDIOM_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_DATABASE, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        return DEFAULT_DATABASE
    try:
        with open(IDIOM_JSON_PATH, "r", encoding="utf-8") as f:
            full_data = json.load(f)
        valid = [item for item in full_data
                 if isinstance(item, dict)
                 and isinstance(item.get("word"), str)
                 and len(item["word"]) == 4]
        if len(valid) < 20:
            existing_words = {item["word"] for item in valid}
            for item in DEFAULT_DATABASE:
                if item["word"] not in existing_words:
                    valid.append(item)
        return valid
    except Exception:
        return DEFAULT_DATABASE


# ===========================================================================
# 游戏主界面
# ===========================================================================
OPTION_COLORS = {
    "normal": (1, 1, 1, 1),
    "correct": (0.18, 0.80, 0.44, 1),
    "wrong": (0.93, 0.28, 0.23, 1),
}

TOTAL_QUESTIONS_PER_ROUND = 10
SCORE_PER_QUESTION = 10

IDIOM_FONT_SIZE = 48 if not IS_MOBILE else 42
BLANK_CHAR = "□"
BLANK_SCALE = 1.4
BLANK_COLOR = (0.90, 0.22, 0.21, 1)


def _safe_get(d, key, default="暂无"):
    v = d.get(key)
    if v is None:
        return default
    v = str(v).strip()
    return v if v else default


_TONE_MAP = str.maketrans({
    "ā": "a", "á": "a", "ǎ": "a", "à": "a",
    "ō": "o", "ó": "o", "ǒ": "o", "ò": "o",
    "ē": "e", "é": "e", "ě": "e", "è": "e",
    "ī": "i", "í": "i", "ǐ": "i", "ì": "i",
    "ū": "u", "ú": "u", "ǔ": "u", "ù": "u",
    "ǖ": "v", "ǘ": "v", "ǚ": "v", "ǜ": "v", "ü": "v",
})


def _strip_tone(text):
    return text.translate(_TONE_MAP).replace(" ", "")


class IdiomGameScreen(MDScreen):

    score_text = StringProperty(f"第1题 / 共{TOTAL_QUESTIONS_PER_ROUND}题 | 得分: 0")
    question_prompt = StringProperty("请选出填入方框的正确字：")
    display_idiom = StringProperty("")
    feedback_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.idiom_list = load_idiom_database()
        self.char_pool = self._build_char_pool_from(self.idiom_list)
        self._search_index = None
        self.question_queue = []
        self.current_question_index = 0
        self.answer_records = []
        self.score = 0
        self.current_idiom = None
        self.target_char = ""
        self.current_fill_pos = 1
        self.history_question_stack = []
        self.answered = False

        self.detail_dialog = None
        self.result_dialog = None
        self.tip_dialog = None
        self.search_dialog = None
        self.wrong_dialog = None

        self.option_buttons = []
        self.option_texts = []

        self._build_ui()
        self._start_new_round()

        Window.bind(on_resize=self._on_window_resize)
        init_sounds()

    def _on_window_resize(self, *args):
        global SCALE
        SCALE = get_scale_factor()

    def _make_button(self, text, bg_color, on_press, font_size=16, height=None):
        if height is None:
            height = sdp(44)
        btn = MDButton(
            style="filled", theme_bg_color="Custom", md_bg_color=bg_color,
            theme_width="Custom", size_hint=(1, None), height=height,
            radius=[sdp(12), sdp(12), sdp(12), sdp(12)],
        )
        btn.add_widget(MDButtonText(
            text=text, font_size=ssp(font_size), bold=True,
            theme_font_size="Custom", theme_font_name="Custom",
            font_name=ZH_FONT_NAME,
        ))
        btn.bind(on_release=on_press)
        return btn

    def _build_ui(self):
        root = MDBoxLayout(
            orientation="vertical", size_hint=(1, 1),
            padding=[sdp(12), sdp(14), sdp(12), sdp(10)],
            spacing=sdp(6), md_bg_color=(0.96, 0.96, 0.98, 1),
        )

        # 标题栏
        title_label = MDLabel(
            text="成语填空测试", font_size=ssp(21), bold=True,
            halign="center", size_hint_y=None, height=sdp(36),
            text_color=(0.17, 0.18, 0.3, 1),
            theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
        )
        root.add_widget(title_label)

        # 得分板
        score_label = MDLabel(
            text=self.score_text, font_size=ssp(13), bold=True,
            halign="center", size_hint_y=None, height=sdp(24),
            text_color=(0.35, 0.35, 0.4, 1),
            theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
        )
        self.bind(score_text=score_label.setter("text"))
        root.add_widget(score_label)

        # 题目卡片
        card_height = sdp(156)
        question_card = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=card_height,
            padding=[sdp(12), sdp(6), sdp(12), sdp(6)], spacing=sdp(3),
            md_bg_color=(1, 1, 1, 1), radius=[sdp(14), sdp(14), sdp(14), sdp(14)],
        )
        prompt_label = MDLabel(
            text=self.question_prompt, font_size=ssp(14), bold=True,
            halign="center", size_hint_y=None, height=sdp(26),
            text_color=(0.25, 0.25, 0.3, 1),
            theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
        )
        self.bind(question_prompt=prompt_label.setter("text"))

        char_layout_height = sdp(104)
        self.idiom_chars_layout = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=char_layout_height,
            spacing=sdp(6), pos_hint={"center_y": 0.5},
        )
        self.idiom_char_widgets = []
        for i in range(4):
            char_box = MDBoxLayout(orientation="vertical", size_hint_x=0.25)
            char_label = MDLabel(
                text="", font_size=ssp(IDIOM_FONT_SIZE), bold=True,
                halign="center", valign="middle", text_color=(0.17, 0.18, 0.3, 1),
                theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
            )
            char_box.add_widget(char_label)
            self.idiom_chars_layout.add_widget(char_box)
            self.idiom_char_widgets.append(char_label)

        question_card.add_widget(prompt_label)
        question_card.add_widget(self.idiom_chars_layout)
        root.add_widget(question_card)

        # 浮动+10分提示标签（答对时弹出动画）
        self.popup_score_label = MDLabel(
            text="", font_size=ssp(22), bold=True, halign="center",
            size_hint_y=None, height=sdp(0), opacity=0,
            text_color=(1.0, 0.55, 0.0, 1),
            theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
        )
        root.add_widget(self.popup_score_label)

        # 选项区：2x2
        options_height = sdp(156)
        options_grid = MDGridLayout(
            cols=2, size_hint_y=None, height=options_height,
            spacing=sdp(8), padding=[0, sdp(2), 0, sdp(2)],
        )
        option_btn_size = sdp(70)
        for i in range(4):
            btn = MDButton(
                style="filled", theme_bg_color="Custom", md_bg_color=(1, 1, 1, 1),
                theme_width="Custom", size_hint_y=None, height=option_btn_size,
                radius=[sdp(12), sdp(12), sdp(12), sdp(12)],
            )
            btn_text = MDButtonText(
                text="", font_size=ssp(28), bold=True, theme_text_color="Custom",
                text_color=(0.17, 0.18, 0.3, 1),
                theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
            )
            btn.add_widget(btn_text)
            btn.bind(on_release=lambda inst, idx=i: self.check_answer(idx))
            self.option_buttons.append(btn)
            self.option_texts.append(btn_text)
            options_grid.add_widget(btn)
        root.add_widget(options_grid)

        # 反馈提示
        feedback_label = MDLabel(
            text=self.feedback_text, font_size=ssp(14), bold=True,
            halign="center", size_hint_y=None, height=sdp(28),
            theme_font_size="Custom", theme_font_name="Custom", font_name=ZH_FONT_NAME,
        )
        self.feedback_label = feedback_label
        self.bind(feedback_text=feedback_label.setter("text"))
        root.add_widget(feedback_label)

        # 功能按钮区（详解/查找/错题本）
        btn_height = sdp(44)
        func_row1 = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=btn_height,
            spacing=sdp(6),
        )
        func_row1.add_widget(self._make_button("查看成语详解", (0.20, 0.59, 0.85, 1),
                                               lambda *a: self.show_idiom_detail(),
                                               font_size=14, height=btn_height))
        func_row1.add_widget(self._make_button("成语查找", (0.58, 0.35, 0.90, 1),
                                               lambda *a: self.show_idiom_search(),
                                               font_size=14, height=btn_height))
        root.add_widget(func_row1)

        func_row2 = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=btn_height,
            spacing=sdp(6),
        )
        func_row2.add_widget(self._make_button("📕 错题本复习", (0.90, 0.35, 0.30, 1),
                                               lambda *a: self.show_wrong_book(),
                                               font_size=14, height=btn_height))
        func_row2.add_widget(self._make_button("重新开始", (0.55, 0.60, 0.62, 1),
                                               lambda *a: self._start_new_round(),
                                               font_size=14, height=btn_height))
        root.add_widget(func_row2)

        # 底部导航按钮
        bottom_height = sdp(46)
        bottom_layout = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=bottom_height,
            spacing=sdp(6), padding=[0, 0, 0, 0],
        )
        bottom_layout.add_widget(self._make_button("上一题", (0.95, 0.61, 0.07, 1),
                                                   lambda *a: self.load_previous_question(),
                                                   font_size=14, height=bottom_height))
        bottom_layout.add_widget(self._make_button("下一题", (0.18, 0.80, 0.44, 1),
                                                   lambda *a: self.load_next_question(),
                                                   font_size=14, height=bottom_height))
        root.add_widget(bottom_layout)

        # 末尾放一个弹性占位吸收多余高度，让全部内容整体贴住窗口顶部，
        # 消除顶部大片空白（垂直堆叠默认把多余空间留在顶部）
        root.add_widget(Widget(size_hint_y=1))

        self.add_widget(root)

    # ------------------------------------------------------------------
    # +10分浮动动画提示
    # ------------------------------------------------------------------
    def _show_score_popup(self, text, color=(1.0, 0.55, 0.0, 1)):
        """答对/答错时弹出+10/-0提示，动画上浮消失"""
        self.popup_score_label.text = text
        self.popup_score_label.text_color = color
        self.popup_score_label.opacity = 1
        self.popup_score_label.height = sdp(28)
        # 动画：向上飘+淡出
        anim = Animation(opacity=0, duration=1.0)
        anim.bind(on_complete=lambda *a: setattr(self.popup_score_label, "height", sdp(0)))
        anim.start(self.popup_score_label)

    # ------------------------------------------------------------------
    # 成语显示更新
    # ------------------------------------------------------------------
    def _update_idiom_display(self):
        word = self.current_idiom["word"]
        blank_size = max(1, int(round(IDIOM_FONT_SIZE * BLANK_SCALE * SCALE)))
        for i, label in enumerate(self.idiom_char_widgets):
            if i == self.current_fill_pos:
                label.text = BLANK_CHAR
                label.font_size = ssp(blank_size / SCALE)
                label.text_color = BLANK_COLOR
            else:
                label.text = word[i]
                label.font_size = ssp(IDIOM_FONT_SIZE)
                label.text_color = (0.17, 0.18, 0.3, 1)

    # ------------------------------------------------------------------
    # 轮次管理
    # ------------------------------------------------------------------
    def _start_new_round(self):
        self._close_all_dialogs()
        SPEECH.stop()
        self.history_question_stack.clear()
        self.answer_records = []
        self.score = 0
        self.current_question_index = 0
        self.answered = False

        if len(self.idiom_list) >= TOTAL_QUESTIONS_PER_ROUND:
            self.question_queue = random.sample(self.idiom_list, TOTAL_QUESTIONS_PER_ROUND)
        else:
            self.question_queue = random.choices(self.idiom_list, k=TOTAL_QUESTIONS_PER_ROUND)

        self._load_current_question()
        self._update_score_display()

    def _update_score_display(self):
        current_num = self.current_question_index + 1
        wrong_count = len(load_wrong_book())
        self.score_text = f"第{current_num}题 / 共{TOTAL_QUESTIONS_PER_ROUND}题 | 得分: {self.score} | 错题: {wrong_count}"

    def _snapshot_current(self):
        if not self.current_idiom:
            return None
        return {
            "idiom": self.current_idiom,
            "target_char": self.target_char,
            "fill_pos": self.current_fill_pos,
            "answered": self.answered,
            "index": self.current_question_index,
        }

    def _restore_question_state(self, state):
        if not state:
            return
        self.current_idiom = state["idiom"]
        self.target_char = state["target_char"]
        self.current_fill_pos = state["fill_pos"]
        self.answered = state["answered"]
        self.current_question_index = state["index"]

        self.question_prompt = "请选出填入方框的正确字："
        self._update_idiom_display()
        self._generate_options(self.target_char)

        if self.answered:
            for b in self.option_buttons:
                b.disabled = True
            for i, txt in enumerate(self.option_texts):
                if txt.text == self.target_char:
                    self.option_buttons[i].md_bg_color = OPTION_COLORS["correct"]
                    self.option_texts[i].text_color = (1, 1, 1, 1)
            if self.answer_records[self.current_question_index]:
                self.feedback_text = "回答正确！+10 分"
                self.feedback_label.text_color = (0.15, 0.68, 0.38, 1)
            else:
                self.feedback_text = f"回答错误，正确答案是「{self.target_char}」"
                self.feedback_label.text_color = (0.93, 0.28, 0.23, 1)
        else:
            self.feedback_text = ""

        self._update_score_display()

    # ------------------------------------------------------------------
    # 题目与选项
    # ------------------------------------------------------------------
    def _reset_option_buttons(self):
        for btn, txt in zip(self.option_buttons, self.option_texts):
            btn.disabled = False
            btn.md_bg_color = OPTION_COLORS["normal"]
            txt.text_color = (0.17, 0.18, 0.3, 1)
        self.feedback_text = ""
        self.answered = False

    @staticmethod
    def _build_char_pool_from(idiom_list):
        """汇总题库里出现过的所有汉字，避免每次出题都遍历整库"""
        pool = set()
        for item in idiom_list:
            w = item.get("word", "")
            if isinstance(w, str) and len(w) == 4:
                pool.update(w)
        return pool

    def _generate_options(self, correct_char):
        options = [correct_char]
        all_chars = set(self.char_pool)
        all_chars.discard(correct_char)
        pool = list(all_chars)
        wrong_chars = random.sample(pool, min(3, len(pool))) if pool else []
        common_fillers = "天地人山水风云日月金木水火土春夏秋冬东西南北花鸟鱼虫"
        retry = 0
        while len(wrong_chars) < 3 and retry < 30:
            c = random.choice(common_fillers)
            if c != correct_char and c not in wrong_chars:
                wrong_chars.append(c)
            retry += 1
        options.extend(wrong_chars[:3])
        random.shuffle(options)
        for txt, char in zip(self.option_texts, options):
            txt.text = char

    def _load_current_question(self):
        self._close_detail_dialog()
        SPEECH.stop()
        self._reset_option_buttons()
        self.current_idiom = self.question_queue[self.current_question_index]
        word = self.current_idiom["word"]
        pos = random.choice([1, 2])
        self.current_fill_pos = pos
        self.target_char = word[pos]
        self.question_prompt = "请选出填入方框的正确字："
        self._update_idiom_display()
        self._generate_options(self.target_char)
        self._update_score_display()

    def load_next_question(self):
        self._close_detail_dialog()
        SPEECH.stop()
        snapshot = self._snapshot_current()
        if snapshot:
            self.history_question_stack.append(snapshot)
        if self.current_question_index >= TOTAL_QUESTIONS_PER_ROUND - 1:
            self._show_round_result()
            return
        self.current_question_index += 1
        if self.current_question_index < len(self.answer_records):
            for snap in reversed(self.history_question_stack):
                if snap["index"] == self.current_question_index:
                    self._restore_question_state(snap)
                    break
            else:
                self._load_current_question()
        else:
            self._load_current_question()

    def load_previous_question(self):
        self._close_detail_dialog()
        SPEECH.stop()
        if self.current_question_index <= 0:
            self._show_tip("已经是第一道题啦")
            return
        snapshot = self._snapshot_current()
        if snapshot:
            self.history_question_stack.append(snapshot)
        self.current_question_index -= 1
        for snap in reversed(self.history_question_stack):
            if snap["index"] == self.current_question_index:
                self._restore_question_state(snap)
                break

    # ------------------------------------------------------------------
    # 判题（带音效+分数弹出提示+错题收集）
    # ------------------------------------------------------------------
    def check_answer(self, index):
        if not (0 <= index < len(self.option_buttons)):
            return
        btn = self.option_buttons[index]
        if btn.disabled or self.answered:
            return

        selected_char = self.option_texts[index].text
        self.answered = True
        for b in self.option_buttons:
            b.disabled = True

        is_correct = (selected_char == self.target_char)
        if is_correct:
            self.score += SCORE_PER_QUESTION
            self.feedback_text = "回答正确！+10 分 🎉"
            self.feedback_label.text_color = (0.15, 0.68, 0.38, 1)
            btn.md_bg_color = OPTION_COLORS["correct"]
            self.option_texts[index].text_color = (1, 1, 1, 1)
            play_correct_sound()
            self._show_score_popup("+10 分！答对啦！", color=(0.15, 0.68, 0.38, 1))
        else:
            self.feedback_text = f"回答错误，正确答案是「{self.target_char}」"
            self.feedback_label.text_color = (0.93, 0.28, 0.23, 1)
            btn.md_bg_color = OPTION_COLORS["wrong"]
            self.option_texts[index].text_color = (1, 1, 1, 1)
            for i, b in enumerate(self.option_buttons):
                if self.option_texts[i].text == self.target_char:
                    b.md_bg_color = OPTION_COLORS["correct"]
                    self.option_texts[i].text_color = (1, 1, 1, 1)
            play_wrong_sound()
            self._show_score_popup("答错了，加油！", color=(0.93, 0.28, 0.23, 1))
            # 答错自动加入错题本
            add_to_wrong_book(self.current_idiom)

        if len(self.answer_records) <= self.current_question_index:
            self.answer_records.append(is_correct)
        else:
            self.answer_records[self.current_question_index] = is_correct

        self._update_score_display()

        if self.current_question_index >= TOTAL_QUESTIONS_PER_ROUND - 1:
            Clock.schedule_once(lambda dt: self._show_round_result(), 1.2)

    # ------------------------------------------------------------------
    # 结算弹窗
    # ------------------------------------------------------------------
    def _show_round_result(self):
        self._close_all_dialogs()
        SPEECH.stop()
        correct_count = sum(self.answer_records)
        total_count = TOTAL_QUESTIONS_PER_ROUND
        accuracy = int(correct_count / total_count * 100)
        final_score = self.score
        wrong_total = len(load_wrong_book())

        if final_score == 100:
            comment = "太棒了！全部答对，成语大师就是你🎉"
        elif final_score >= 80:
            comment = "成绩优秀！继续加油哦👏"
        elif final_score >= 60:
            comment = "及格啦，还有进步空间💪"
        else:
            comment = "还要多多练习哦📚"

        result_text = (
            f"本轮测试结束！\n\n"
            f"最终得分：{final_score} 分（满分100分）\n"
            f"答对题数：{correct_count} / {total_count} 题\n"
            f"正确率：{accuracy}%\n"
            f"累计错题：{wrong_total} 个\n\n"
            f"{comment}"
        )

        self.result_dialog = MDDialog(
            MDDialogHeadlineText(
                text="测试结果", halign="center",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogSupportingText(
                text=result_text, halign="center",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="查看错题", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: (self._close_result_dialog(), self.show_wrong_book()),
                ),
                MDButton(
                    MDButtonText(text="开始下一轮", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="filled", theme_width="Custom",
                    on_release=lambda *a: self._start_new_round(),
                ),
                spacing="8dp",
            ),
        )
        self.result_dialog.bind(on_dismiss=lambda *a: setattr(self, "result_dialog", None))
        self.result_dialog.open()

    # ------------------------------------------------------------------
    # 对话框管理
    # ------------------------------------------------------------------
    def _close_all_dialogs(self):
        self._close_detail_dialog()
        self._close_tip()
        self._close_result_dialog()
        self._close_search_dialog()
        self._close_wrong_dialog()

    def _on_detail_dismiss(self, *a):
        try:
            SPEECH.stop()
        except Exception:
            pass
        self.detail_dialog = None

    def _close_detail_dialog(self):
        if self.detail_dialog is not None:
            try: self.detail_dialog.dismiss()
            except: pass
            self.detail_dialog = None

    def _close_tip(self):
        if self.tip_dialog is not None:
            try: self.tip_dialog.dismiss()
            except: pass
            self.tip_dialog = None

    def _close_result_dialog(self):
        if self.result_dialog is not None:
            try: self.result_dialog.dismiss()
            except: pass
            self.result_dialog = None

    def _close_search_dialog(self):
        if self.search_dialog is not None:
            try: self.search_dialog.dismiss()
            except: pass
            self.search_dialog = None

    def _close_wrong_dialog(self):
        if self.wrong_dialog is not None:
            try: self.wrong_dialog.dismiss()
            except: pass
            self.wrong_dialog = None

    def _show_tip(self, message):
        self._close_tip()
        self.tip_dialog = MDDialog(
            MDDialogHeadlineText(text="提示", theme_font_name="Custom", font_name=ZH_FONT_NAME),
            MDDialogSupportingText(text=message, theme_font_name="Custom", font_name=ZH_FONT_NAME),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="知道了", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: self._close_tip(),
                ),
                spacing="8dp",
            ),
        )
        self.tip_dialog.bind(on_dismiss=lambda *a: setattr(self, "tip_dialog", None))
        self.tip_dialog.open()

    # ------------------------------------------------------------------
    # 成语详情弹窗（含例句朗读）
    # ------------------------------------------------------------------
    def show_idiom_detail(self, idiom=None):
        if idiom is None:
            idiom = self.current_idiom
        if not idiom:
            self._show_tip("当前还没有题目哦～")
            return
        self._close_detail_dialog()
        SPEECH.stop()

        word = _safe_get(idiom, "word")
        pinyin = _safe_get(idiom, "pinyin")
        explanation = _safe_get(idiom, "explanation")
        derivation = _safe_get(idiom, "derivation")
        example = _safe_get(idiom, "example", default="")

        lines = [f"【拼音】 {pinyin}", "", f"【释义】 {explanation}", "", f"【出处】 {derivation}"]
        if example and example != "暂无":
            lines.extend(["", f"【例句】 {example}"])
        info_text = "\n".join(lines)

        # 朗读文本包含例句
        speak_text = _build_speak_text(word, pinyin, explanation, example)

        self.detail_dialog = MDDialog(
            MDDialogHeadlineText(
                text=f"成语详解 · {word}", halign="center",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogSupportingText(
                text=info_text, halign="left",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="🔊 朗读", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: SPEECH.speak(speak_text),
                ),
                MDButton(
                    MDButtonText(text="关闭", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: self._close_detail_dialog(),
                ),
                spacing="6dp",
            ),
        )
        self.detail_dialog.bind(on_dismiss=self._on_detail_dismiss)
        self.detail_dialog.open()

        # 打开详解自动朗读一次（含例句）
        SPEECH.speak(speak_text)

    # ------------------------------------------------------------------
    # 错题本弹窗
    # ------------------------------------------------------------------
    def show_wrong_book(self):
        self._close_wrong_dialog()
        wrong_dict = load_wrong_book()

        dialog_height = sdp(400)
        content = MDBoxLayout(
            orientation="vertical", spacing=sdp(6),
            padding=[sdp(6), sdp(6), sdp(6), sdp(6)],
            size_hint_y=None, height=dialog_height,
        )

        scroll = MDScrollView(
            size_hint_y=1, do_scroll_x=False, do_scroll_y=True,
            bar_width=sdp(4) if IS_MOBILE else 0,
        )
        result_layout = MDBoxLayout(
            orientation="vertical", spacing=sdp(6), size_hint_y=None,
            padding=[sdp(4), sdp(4)],
        )
        result_layout.bind(minimum_height=result_layout.setter("height"))

        if not wrong_dict:
            hint = Label(
                text="太棒了！还没有错题，继续保持🎉",
                halign="center", valign="middle",
                font_name=ZH_FONT_NAME, font_size=ssp(14),
                color=(0.3, 0.6, 0.3, 1), size_hint_y=None, height=sdp(100),
            )
            hint.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], sdp(100))))
            result_layout.add_widget(hint)
        else:
            # 建一个word->idiom的查找表
            idiom_map = {item["word"]: item for item in self.idiom_list}
            # 按错误次数排序
            sorted_words = sorted(wrong_dict.items(), key=lambda x: -x[1])
            item_height = sdp(70)
            for word, count in sorted_words:
                idiom = idiom_map.get(word, {"word": word, "pinyin": "", "explanation": "（题库中暂无该成语详解）",
                                             "derivation": "", "example": ""})
                pinyin = _safe_get(idiom, "pinyin")
                explanation = _safe_get(idiom, "explanation")
                exp_short = explanation if len(explanation) <= 18 else explanation[:18] + "…"
                item = Button(
                    text=f"{word}（错{count}次）  {pinyin}\n{exp_short}",
                    size_hint_y=None, height=item_height,
                    font_name=ZH_FONT_NAME, font_size=ssp(14),
                    color=(0.3, 0.15, 0.15, 1),
                    background_normal="", background_down="",
                    background_color=(0.98, 0.90, 0.90, 1),
                    halign="left", valign="middle",
                    padding=[sdp(10), sdp(6)],
                )
                item.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0] - sdp(20), None)))
                item.bind(on_release=lambda inst, idm=idiom: self.show_idiom_detail(idm))
                result_layout.add_widget(item)

            # 清空错题本按钮
            clear_btn = Button(
                text="🗑 清空错题本", size_hint_y=None, height=sdp(44),
                font_name=ZH_FONT_NAME, font_size=ssp(14), bold=True,
                color=(1, 1, 1, 1),
                background_normal="", background_down="",
                background_color=(0.80, 0.30, 0.30, 1),
            )
            clear_btn.bind(on_release=lambda *a: self._clear_wrong_book())
            result_layout.add_widget(clear_btn)

        scroll.add_widget(result_layout)
        content.add_widget(scroll)

        count = len(wrong_dict)
        self.wrong_dialog = MDDialog(
            MDDialogHeadlineText(
                text=f"📕 错题本（共{count}个）", halign="center",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="关闭", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: self._close_wrong_dialog(),
                ),
                spacing="8dp",
            ),
            auto_dismiss=False,
        )
        self.wrong_dialog.bind(on_dismiss=lambda *a: setattr(self, "wrong_dialog", None))
        self.wrong_dialog.open()

    def _clear_wrong_book(self):
        """清空错题本"""
        save_wrong_book({})
        self._close_wrong_dialog()
        self._update_score_display()
        self._show_tip("错题本已清空")

    # ------------------------------------------------------------------
    # 成语查找功能
    # ------------------------------------------------------------------
    def show_idiom_search(self):
        self._close_search_dialog()
        dialog_height = sdp(380) if IS_MOBILE else sdp(340)
        content = MDBoxLayout(
            orientation="vertical", spacing=sdp(8),
            padding=[sdp(6), sdp(6), sdp(6), sdp(6)],
            size_hint_y=None, height=dialog_height,
        )

        self.search_input = TextInput(
            hint_text="输入拼音或汉字，如 cu / fang / 防",
            multiline=False, size_hint_y=None, height=sdp(44),
            font_size=ssp(16), font_name=ZH_FONT_NAME,
            padding=[sdp(12), sdp(10), sdp(12), sdp(8)],
            background_color=(0.95, 0.95, 0.97, 1),
            foreground_color=(0.15, 0.15, 0.25, 1),
            cursor_color=(0.2, 0.4, 0.9, 1), cursor_width=ssp(1.4),
            write_tab=False,
        )
        if IS_MOBILE:
            self.search_input.use_bubble = True
            self.search_input.use_handles = True
        else:
            self.search_input.use_bubble = False
            self.search_input.use_handles = False
        content.add_widget(self.search_input)

        scroll_height = dialog_height - sdp(44) - sdp(16)
        self.search_result_scroll = MDScrollView(
            size_hint_y=None, height=scroll_height,
            do_scroll_x=False, do_scroll_y=True,
            bar_width=sdp(4) if IS_MOBILE else 0,
        )
        self.search_result_layout = MDBoxLayout(
            orientation="vertical", spacing=sdp(6), size_hint_y=None,
            padding=[sdp(4), sdp(4)],
        )
        self.search_result_layout.bind(minimum_height=self.search_result_layout.setter("height"))
        self.search_result_scroll.add_widget(self.search_result_layout)
        content.add_widget(self.search_result_scroll)

        self._show_search_hint("输入拼音或汉字后，下方自动列出候选")

        self.search_dialog = MDDialog(
            MDDialogHeadlineText(
                text="成语查找", halign="center",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="搜索", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="filled", theme_width="Custom",
                    on_release=lambda *a: self.do_search_idiom(),
                ),
                MDButton(
                    MDButtonText(text="关闭", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: self._close_search_dialog(),
                ),
                spacing="12dp",
            ),
            auto_dismiss=False,
        )

        self.search_input.bind(text=lambda inst, val: self.do_search_idiom(live=True))
        self.search_input.bind(on_text_validate=lambda *a: self.do_search_idiom())
        self.search_dialog.bind(on_dismiss=lambda *a: setattr(self, "search_dialog", None))
        self.search_dialog.open()

        def _focus_input(dt):
            try:
                self.search_input.focus = True
            except Exception:
                pass
        Clock.schedule_once(_focus_input, 0.3)

    def _show_search_hint(self, text):
        self.search_result_layout.clear_widgets()
        hint = Label(
            text=text, halign="center", valign="middle",
            font_name=ZH_FONT_NAME, font_size=ssp(13),
            color=(0.5, 0.5, 0.55, 1), size_hint_y=None, height=sdp(60),
        )
        hint.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], sdp(60))))
        self.search_result_layout.add_widget(hint)

    @staticmethod
    def _split_search_terms(keyword):
        raw = keyword.strip().replace("'", " ").replace("’", " ").replace("-", " ")
        parts = [p for p in raw.split() if p]
        whole_plain = _strip_tone(keyword).replace("'", "").replace("’", "").replace(" ", "").lower()
        return parts, whole_plain

    def _ensure_search_index(self):
        """懒加载搜索索引：预先把每个成语的可检索文本算好，避免每次输入都重复解析整库"""
        if self._search_index is None:
            index = []
            for idiom in self.idiom_list:
                word = _safe_get(idiom, "word", "")
                pinyin_plain = _strip_tone(_safe_get(idiom, "pinyin", "").lower())
                exp_plain = _strip_tone(_safe_get(idiom, "explanation", "")).lower()
                der_plain = _strip_tone(_safe_get(idiom, "derivation", "")).lower()
                index.append((idiom, word, pinyin_plain, exp_plain, der_plain))
            self._search_index = index
        return self._search_index

    def do_search_idiom(self, live=False):
        if not hasattr(self, "search_input") or not self.search_input:
            return
        keyword = self.search_input.text.strip()
        if not keyword:
            self._show_search_hint("输入拼音或汉字后，下方自动列出候选")
            return

        results = []
        _, whole_plain = self._split_search_terms(keyword)
        keyword_clean = keyword.replace(" ", "")
        terms, _ = self._split_search_terms(keyword)
        term_plain_list = [_strip_tone(t).lower() for t in terms if t]
        keyword_lower_plain = _strip_tone(keyword).lower()

        for idiom, word, pinyin_plain, exp_plain, der_plain in self._ensure_search_index():
            matched = False
            if any("\u4e00" <= ch <= "\u9fff" for ch in keyword):
                if keyword_clean in word or any(ch in word for ch in keyword_clean
                                                if "\u4e00" <= ch <= "\u9fff"):
                    matched = True
            if not matched and whole_plain:
                if pinyin_plain.startswith(whole_plain) or whole_plain in pinyin_plain:
                    matched = True
            if not matched and term_plain_list:
                matched = self._match_char_pinyin(pinyin_plain, term_plain_list)
            if not matched and keyword_lower_plain:
                if keyword_lower_plain in exp_plain or keyword_lower_plain in der_plain:
                    matched = True
            if matched:
                results.append(idiom)

        if whole_plain:
            def _rank(it):
                py = _strip_tone(_safe_get(it, "pinyin", "")).lower()
                return 0 if py.startswith(whole_plain) else 1
            results.sort(key=_rank)

        results = results[:40]

        if not results:
            self._show_search_hint(f"没有匹配「{keyword}」的成语，试试 cu、fang 或单个汉字")
            return
        self._render_search_results(results)

    @staticmethod
    def _match_char_pinyin(pinyin_plain, term_list):
        pos = 0
        for term in term_list:
            idx = pinyin_plain.find(term, pos)
            if idx == -1:
                return False
            pos = idx + len(term)
        return True

    def _render_search_results(self, results):
        self.search_result_layout.clear_widgets()
        item_height = sdp(70) if not IS_MOBILE else sdp(80)
        for idiom in results:
            word = _safe_get(idiom, "word")
            pinyin = _safe_get(idiom, "pinyin")
            explanation = _safe_get(idiom, "explanation")
            exp_short = explanation if len(explanation) <= 20 else explanation[:20] + "…"

            item = Button(
                text=f"{word}   {pinyin}\n{exp_short}",
                size_hint_y=None, height=item_height,
                font_name=ZH_FONT_NAME, font_size=ssp(14),
                color=(0.14, 0.18, 0.34, 1),
                background_normal="", background_down="",
                background_color=(0.93, 0.94, 0.98, 1),
                halign="left", valign="middle",
                padding=[sdp(12), sdp(8)],
            )
            item.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0] - sdp(24), None)))
            item.bind(on_release=lambda inst, idm=idiom: self.show_searched_idiom_detail(idm))
            self.search_result_layout.add_widget(item)

        count_hint = Label(
            text=f"共 {len(results)} 个候选，点击查看详情",
            halign="center", valign="middle",
            font_name=ZH_FONT_NAME, font_size=ssp(12),
            color=(0.5, 0.5, 0.6, 1), size_hint_y=None, height=sdp(30),
        )
        count_hint.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], sdp(30))))
        self.search_result_layout.add_widget(count_hint)

    def show_searched_idiom_detail(self, idiom):
        """查找结果点开详情（同样支持例句朗读）"""
        word = _safe_get(idiom, "word")
        pinyin = _safe_get(idiom, "pinyin")
        explanation = _safe_get(idiom, "explanation")
        derivation = _safe_get(idiom, "derivation")
        example = _safe_get(idiom, "example", default="")

        lines = [f"【拼音】 {pinyin}", "", f"【释义】 {explanation}", "", f"【出处】 {derivation}"]
        if example and example != "暂无":
            lines.extend(["", f"【例句】 {example}"])
        info_text = "\n".join(lines)
        speak_text = _build_speak_text(word, pinyin, explanation, example)

        detail = MDDialog(
            MDDialogHeadlineText(
                text=word, halign="center",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogSupportingText(
                text=info_text, halign="left",
                theme_font_name="Custom", font_name=ZH_FONT_NAME,
            ),
            MDDialogButtonContainer(
                MDButton(
                    MDButtonText(text="🔊 朗读", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: SPEECH.speak(speak_text),
                ),
                MDButton(
                    MDButtonText(text="返回查找", theme_font_name="Custom", font_name=ZH_FONT_NAME),
                    style="text", theme_width="Custom",
                    on_release=lambda *a: self._close_temp_dialog(detail),
                ),
                spacing="6dp",
            ),
        )

        detail.bind(on_dismiss=lambda *a: SPEECH.stop())
        detail.open()
        SPEECH.speak(speak_text)

    def _close_temp_dialog(self, dialog):
        try:
            dialog.dismiss()
        except Exception:
            pass


class IdiomGameAppMain(MDApp):

    def build(self):
        self.title = "小学一年级成语测试-蒋沐东专用版"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        apply_chinese_font_to_theme(self.theme_cls)
        if IS_MOBILE:
            Window.borderless = True
        return IdiomGameScreen()

    def on_pause(self):
        try:
            SPEECH.stop()
        except Exception:
            pass
        return True

    def on_resume(self):
        return True


if __name__ == "__main__":
    IdiomGameAppMain().run()
