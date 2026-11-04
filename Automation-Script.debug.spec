# -*- mode: python ; coding: utf-8 -*-
# 精简版 spec：排除 torch / CUDA 及与本脚本无关的重型 ML 依赖
# 原始脚本仅用到 pyautogui / pynput / pystray / PIL / rapidocr / pytesseract / numpy / opencv

from PyInstaller.utils.hooks import collect_data_files

# rapidocr 的 ONNX 模型与 config.yaml 属于包内数据文件，必须显式收集
datas = []
try:
    datas += collect_data_files('rapidocr_onnxruntime')
except Exception:
    pass
try:
    datas += collect_data_files('rapidocr')
except Exception:
    pass

# 外部 Tesseract 作为可选回退，仅在系统存在时由 pytesseract 调用，不打入包内

EXCLUDES = [
    # torch 与 CUDA 全家桶（2.2GB 体积主因）
    'torch', 'torchvision', 'torchaudio', 'torchgen', 'functorch', 'triton',
    'nvidia', 'cupy', 'cudatoolkit', 'torch._dynamo',
    # 训练 / NLP / 数据处理重型依赖
    'transformers', 'tokenizers', 'accelerate', 'peft', 'safetensors', 'datasets',
    'huggingface_hub', 'modelscope', 'bitsandbytes', 'auto_gptq', 'sentencepiece',
    'ultralytics', 'ultralytics_thop', 'lightgbm', 'scipy', 'pandas', 'sklearn',
    'scikit_learn', 'seaborn', 'statsmodels', 'patsy', 'matplotlib', 'sympy',
    'networkx', 'polars', 'pyarrow', 'joblib', 'threadpoolctl', 'contourpy',
    'fontTools', 'kiwisolver', 'cycler', 'mpmath', 'xxhash', 'tqdm',
    # Web / 服务 / 其它无关框架
    'flask', 'werkzeug', 'jinja2', 'MarkupSafe', 'itsdangerous', 'click', 'blinker',
    'paramiko', 'bcrypt', 'nacl', 'cryptography', 'sounddevice',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'PyQtWebEngine',
    'IPython', 'jedi', 'parso', 'prompt_toolkit', 'stack_data', 'asttokens',
    'executing', 'pure_eval', 'traitlets', 'pygments', 'Pygments',
    'pytest', 'setuptools', 'pip', 'wheel', 'pkg_resources', '_distutils_hack',
    'tkinter.test', 'test', 'unittest',
    'pydoc_data',
]

a = Analysis(
    ['Automation-Script.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['rapidocr_onnxruntime', 'rapidocr_onnxruntime.main', 'cv2', 'pyclipper', 'shapely'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Automation-Script-debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
