import pyautogui
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import json
import os
import sys
import ctypes
import traceback
import copy
import datetime
import itertools
import random
import math
import re
import shlex
import shutil
import subprocess
import tempfile

SLEEP_INTERVAL = 0.01

PYNPUT_AVAILABLE = False
try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Listener as MouseListener
    from pynput.keyboard import Key, Listener as KeyboardListener
    PYNPUT_AVAILABLE = True
except ImportError as e:
    PYNPUT_AVAILABLE = False

PYSTRAY_AVAILABLE = False
try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

OCR_AVAILABLE = False
OCR_BACKEND = None
try:
    from rapidocr import RapidOCR
    OCR_AVAILABLE = True
    OCR_BACKEND = 'rapidocr'
except ImportError:
    try:
        from rapidocr_onnxruntime import RapidOCR
        OCR_AVAILABLE = True
        OCR_BACKEND = 'rapidocr_onnxruntime'
    except ImportError:
        try:
            import pytesseract
            if os.path.exists(r'E:\Tesseract-OCR\tesseract.exe'):
                pytesseract.pytesseract.tesseract_cmd = r'E:\Tesseract-OCR\tesseract.exe'
            if os.path.exists(r'E:\Tesseract-OCR\tessdata'):
                os.environ['TESSDATA_PREFIX'] = r'E:\Tesseract-OCR\tessdata'
            OCR_AVAILABLE = True
            OCR_BACKEND = 'pytesseract'
        except ImportError:
            OCR_AVAILABLE = False
            OCR_BACKEND = None

def _safe_eval_template(expr, ctx):
    import ast as _ast
    allowed_funcs = {'random': random, 'math': math, 'abs': abs, 'min': min, 'max': max,
                     'int': int, 'float': float, 'str': str}
    allowed_attr_bases = {'random', 'math'}

    def _check(node):
        if isinstance(node, _ast.Expression):
            _check(node.body)
        elif isinstance(node, _ast.Name):
            if node.id not in ctx and node.id not in allowed_funcs:
                raise ValueError("不允许的变量: %s" % node.id)
        elif isinstance(node, _ast.Attribute):
            if not (isinstance(node.value, _ast.Name) and node.value.id in allowed_attr_bases):
                raise ValueError("不允许的属性访问: %s" % node.attr)
            _check(node.value)
        elif isinstance(node, _ast.Constant):
            return
        elif isinstance(node, _ast.Call):
            _check(node.func)
            for a in node.args:
                _check(a)
            for kw in node.keywords:
                _check(kw.value)
        elif isinstance(node, (_ast.BinOp, _ast.UnaryOp, _ast.Compare, _ast.BoolOp)):
            for child in _ast.iter_child_nodes(node):
                _check(child)
        elif isinstance(node, (_ast.operator, _ast.cmpop, _ast.boolop, _ast.unaryop, _ast.Load, _ast.keyword)):
            return
        else:
            raise ValueError("不允许的表达式节点: %s" % type(node).__name__)

    tree = _ast.parse(expr, mode='eval')
    _check(tree)
    return eval(compile(tree, '<template>', 'eval'), {"__builtins__": {}}, dict(ctx, **allowed_funcs))


class AutoClicker:
    def __init__(self):
        self.running = False
        self.stop_event = threading.Event()
        self.paused_event = threading.Event()
        self.actions = []
        self.current_action_index = 0
        self.gui_instance = None
        
        self._lock = threading.Lock()

        self.clipboard_poll_interval = 0.5


        self.vars = {
            'screen_w': 1920,
            'screen_h': 1080,
            'last_click_x': 0,
            'last_click_y': 0,
            'last_move_x': 0,
            'last_move_y': 0,
            'mouse_x': 0,
            'mouse_y': 0,
            'loop_index': 0,
            'ocr_result': [],
            'ocr_text': '',
        }
        self._update_screen_vars()

        if PYNPUT_AVAILABLE:
            self.mouse_controller = mouse.Controller()
            self.keyboard_controller = keyboard.Controller()
        else:
            self.mouse_controller = None
            self.keyboard_controller = None
        
        self._key_mapping = {
            'space': Key.space,
            'enter': Key.enter,
            'tab': Key.tab,
            'esc': Key.esc,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
            'caps_lock': Key.caps_lock,
            'cmd': Key.cmd,
            'home': Key.home,
            'end': Key.end,
            'page_up': Key.page_up,
            'page_down': Key.page_down,
            'insert': Key.insert,
            'menu': Key.menu,
            'num_lock': Key.num_lock,
            'print_screen': Key.print_screen,
            'scroll_lock': Key.scroll_lock,
            'pause': Key.pause,
            'f1': Key.f1,
            'f2': Key.f2,
            'f3': Key.f3,
            'f4': Key.f4,
            'f5': Key.f5,
            'f6': Key.f6,
            'f7': Key.f7,
            'f8': Key.f8,
            'f9': Key.f9,
            'f10': Key.f10,
            'f11': Key.f11,
            'f12': Key.f12,
        }
        
        self._action_mapping = {
            'move': self.move_mouse,
            'move_rel': self.move_rel,
            'locate_click': self.locate_click,
            'click': self.click_mouse,
            'double_click': self.double_click,
            'right_click': self.right_click,
            'left_click': self.left_click,
            'scroll': self.scroll,
            'press': self.press_key,
            'type': self.type_text,
            'hotkey': self.hotkey,
            'drag': self.drag_mouse,
            'wait': self.wait,
            'hold': self.hold_mouse,
            'key_hold': self.hold_key,
            'multi_key': self.multi_key_press,
            'multi_mouse': self.multi_mouse_press,
            'multi_key_mouse': self.multi_keyboard_mouse_press,
            'fill': self.fill_number,
            'loop': self.execute_loop,
            'conditional': self.execute_conditional,
            'open_file': self.open_file,
            'open_url': self.open_url,
            'ocr_read': self.ocr_read,
            'ocr_click': self.ocr_click,
        }
    
    def _update_screen_vars(self):
        try:
            w, h = pyautogui.size()
            self.vars['screen_w'] = w
            self.vars['screen_h'] = h
        except:
            pass
        try:
            pos = pyautogui.position()
            self.vars['mouse_x'] = pos.x
            self.vars['mouse_y'] = pos.y
        except:
            pass
    

    def _resolve_template(self, value):
        if not isinstance(value, str):
            return value
        
        pattern = re.compile(r'\{\{(.+?)\}\}')
        
        def _eval_expr(expr):
            expr = expr.strip()
            safe_ctx = {
                'vars': self.vars,
                'random': random,
                'math': math,
                'abs': abs,
                'min': min,
                'max': max,
                'int': int,
                'float': float,
                'str': str,
            }
            safe_ctx.update(self.vars)
            try:
                return _safe_eval_template(expr, safe_ctx)
            except Exception as e:
                print(f"变量求值错误 '{{{{{expr}}}}}: {e}")
                return f"{{{{{expr}}}}}"
        
        match = pattern.fullmatch(value)
        if match:
            result = _eval_expr(match.group(1))
            return result
        
        def _replacer(m):
            result = _eval_expr(m.group(1))
            return str(result)
        
        return pattern.sub(_replacer, value)
    
    def _resolve_kwargs(self, kwargs):
        resolved = {}
        for key, value in kwargs.items():
            resolved[key] = self._resolve_template(value)
        return resolved
    
    def _update_vars_after_action(self, action_type, kwargs):
        self._update_screen_vars()
        
        if action_type in ('click', 'double_click', 'right_click', 'left_click'):
            try:
                pos = pyautogui.position()
                self.vars['last_click_x'] = pos.x
                self.vars['last_click_y'] = pos.y
            except:
                pass
        elif action_type == 'move':
            self.vars['last_move_x'] = kwargs.get('x', 0)
            self.vars['last_move_y'] = kwargs.get('y', 0)
            self.vars['last_click_x'] = kwargs.get('x', 0)
            self.vars['last_click_y'] = kwargs.get('y', 0)
        elif action_type == 'move_rel':
            dx = kwargs.get('dx', 0)
            dy = kwargs.get('dy', 0)
            self.vars['last_move_x'] = self.vars.get('last_move_x', 0) + dx
            self.vars['last_move_y'] = self.vars.get('last_move_y', 0) + dy
            self.vars['last_click_x'] = self.vars['last_move_x']
            self.vars['last_click_y'] = self.vars['last_move_y']
        elif action_type == 'drag':
            self.vars['last_move_x'] = kwargs.get('x', 0)
            self.vars['last_move_y'] = kwargs.get('y', 0)

    def _map_key(self, key_str):
        if not PYNPUT_AVAILABLE or not isinstance(key_str, str):
            return key_str
        return self._key_mapping.get(key_str.lower(), key_str)
    
    def _wait_interruptible(self, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            if self.stop_event.is_set():
                return False
            time.sleep(SLEEP_INTERVAL)
        return True
    
    def move_mouse(self, x, y, duration=0):
        try:
            if duration <= 0:
                pyautogui.moveTo(x, y, duration=0)
            else:
                start_x, start_y = pyautogui.position()
                steps = max(1, int(duration * 100))
                step_sleep = duration / steps
                for i in range(1, steps + 1):
                    if self.stop_event.is_set():
                        return False
                    while self.paused_event.is_set() and not self.stop_event.is_set():
                        time.sleep(0.05)
                    t = i / steps
                    cur_x = start_x + (x - start_x) * t
                    cur_y = start_y + (y - start_y) * t
                    pyautogui.moveTo(cur_x, cur_y, duration=0)
                    time.sleep(step_sleep)
            return True
        except Exception as e:
            print(f"移动鼠标出错: {e}")
            return False
    
    def move_rel(self, dx, dy, duration=0):
        try:
            if duration <= 0:
                pyautogui.moveRel(dx, dy, duration=0)
            else:
                if self.stop_event.is_set():
                    return False
                while self.paused_event.is_set() and not self.stop_event.is_set():
                    time.sleep(0.05)
                pyautogui.moveRel(dx, dy, duration=duration)
            return True
        except Exception as e:
            print(f"相对移动鼠标出错: {e}")
            return False
    
    def locate_click(self, image_path, confidence=0.9, offset_x=0, offset_y=0, 
                     clicks=1, button='left', on_fail='skip'):
        if not os.path.exists(image_path):
            print(f"图像识别: 图片不存在 {image_path}")
            return False
        
        max_attempts = 3 if on_fail == 'retry' else 1
        for attempt in range(max_attempts):
            if not self.running:
                return False
            try:
                loc = pyautogui.locateOnScreen(image_path, confidence=confidence)
                if loc:
                    center = pyautogui.center(loc)
                    target_x = center.x + offset_x
                    target_y = center.y + offset_y
                    pyautogui.click(x=target_x, y=target_y, button=button, clicks=clicks, interval=0.1)
                    print(f"图像识别: 已点击 {image_path} 位置({target_x}, {target_y})")
                    return True
                else:
                    print(f"图像识别: 未找到 {image_path} (尝试 {attempt+1}/{max_attempts})")
                    if on_fail == 'retry' and attempt < max_attempts - 1:
                        time.sleep(0.5)
                        continue
            except Exception as e:
                print(f"图像识别出错: {e}")
                if on_fail == 'retry' and attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
        
        if on_fail == 'error':
            raise RuntimeError(f"图像识别失败: 未找到 {image_path}")
        return False

    def click_mouse(self, button='left', clicks=1, interval=0.1):
        try:
            pyautogui.click(button=button, clicks=clicks, interval=interval)
            return True
        except Exception as e:
            print(f"鼠标点击出错: {e}")
            return False
    
    def double_click(self, button='left'):
        return self.click_mouse(button=button, clicks=2, interval=0.1)
    
    def right_click(self):
        return self.click_mouse(button='right')
    
    def left_click(self):
        return self.click_mouse(button='left')
    
    def scroll(self, clicks, direction='vertical'):
        try:
            if direction == 'horizontal':
                pyautogui.hscroll(clicks)
            else:
                pyautogui.scroll(clicks)
            return True
        except AttributeError:
            if direction == 'horizontal':
                pyautogui.keyDown('shift')
                pyautogui.scroll(clicks)
                pyautogui.keyUp('shift')
            else:
                pyautogui.scroll(clicks)
            return True
        except Exception as e:
            print(f"滚动出错: {e}")
            return False
    
    def press_key(self, key, presses=1, interval=0.1):
        try:
            if PYNPUT_AVAILABLE:
                key = self._map_key(key)
                for _ in range(presses):
                    self.keyboard_controller.press(key)
                    self.keyboard_controller.release(key)
                    if interval > 0:
                        start_time = time.time()
                        while time.time() - start_time < interval:
                            if self.stop_event.is_set():
                                break
                            time.sleep(0.01)
            else:
                pyautogui.press(key, presses=presses, interval=interval)
            return True
        except Exception as e:
            print(f"按键出错: {e}")
            return False
    
    def type_text(self, text, interval=0.1):
        try:
            if PYNPUT_AVAILABLE:
                for char in text:
                    self.keyboard_controller.press(char)
                    self.keyboard_controller.release(char)
                    if interval > 0:
                        start_time = time.time()
                        while time.time() - start_time < interval:
                            if self.stop_event.is_set():
                                break
                            time.sleep(0.01)
            else:
                pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            print(f"输入文本出错: {e}")
            return False
    
    def hotkey(self, *keys):
        try:
            if PYNPUT_AVAILABLE:
                mapped_keys = [self._map_key(key) for key in keys]
                
                for key in mapped_keys:
                    self.keyboard_controller.press(key)
                
                for key in reversed(mapped_keys):
                    self.keyboard_controller.release(key)
            else:
                pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"组合键出错: {e}")
            return False
    
    def multi_key_press(self, keys, duration=1.0):
        try:
            if PYNPUT_AVAILABLE:
                key_objects = [self._map_key(key) for key in keys]
                
                for key_obj in key_objects:
                    self.keyboard_controller.press(key_obj)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                
                for key_obj in reversed(key_objects):
                    self.keyboard_controller.release(key_obj)
            else:
                for key in keys:
                    pyautogui.keyDown(key)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                
                for key in reversed(keys):
                    pyautogui.keyUp(key)
            
            return True
        except Exception as e:
            print(f"多按键同步按下出错: {e}")
            return False
    
    def multi_mouse_press(self, buttons, duration=1.0):
        try:
            if PYNPUT_AVAILABLE:
                button_objects = []
                for button in buttons:
                    if button == 'left':
                        btn_obj = Button.left
                    elif button == 'right':
                        btn_obj = Button.right
                    elif button == 'middle':
                        btn_obj = Button.middle
                    else:
                        btn_obj = Button.left
                    button_objects.append(btn_obj)
                
                for btn_obj in button_objects:
                    self.mouse_controller.press(btn_obj)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                
                for btn_obj in reversed(button_objects):
                    self.mouse_controller.release(btn_obj)
            else:
                for button in buttons:
                    pyautogui.mouseDown(button=button)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                
                for button in reversed(buttons):
                    pyautogui.mouseUp(button=button)
            
            return True
        except Exception as e:
            print(f"多鼠标按键同步按下出错: {e}")
            return False
    
    def multi_keyboard_mouse_press(self, keys, buttons, duration=1.0):
        try:
            if PYNPUT_AVAILABLE:
                key_objects = [self._map_key(key) for key in keys]
                
                button_objects = []
                for button in buttons:
                    if button == 'left':
                        btn_obj = Button.left
                    elif button == 'right':
                        btn_obj = Button.right
                    elif button == 'middle':
                        btn_obj = Button.middle
                    else:
                        btn_obj = Button.left
                    button_objects.append(btn_obj)
                
                for key_obj in key_objects:
                    self.keyboard_controller.press(key_obj)
                
                for btn_obj in button_objects:
                    self.mouse_controller.press(btn_obj)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                
                for btn_obj in reversed(button_objects):
                    self.mouse_controller.release(btn_obj)
                
                for key_obj in reversed(key_objects):
                    self.keyboard_controller.release(key_obj)
            else:
                for key in keys:
                    pyautogui.keyDown(key)
                
                for button in buttons:
                    pyautogui.mouseDown(button=button)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                
                for button in reversed(buttons):
                    pyautogui.mouseUp(button=button)
                
                for key in reversed(keys):
                    pyautogui.keyUp(key)
            
            return True
        except Exception as e:
            print(f"键盘与鼠标同时按下出错: {e}")
            return False
    
    def drag_mouse(self, x, y, duration=0, button='left'):
        try:

            if duration <= 0:
                pyautogui.mouseDown(button=button)
                pyautogui.moveTo(x, y, duration=0)
                pyautogui.mouseUp(button=button)
            else:
                start_x, start_y = pyautogui.position()
                steps = max(1, int(duration * 100))
                step_sleep = duration / steps
                pyautogui.mouseDown(button=button)
                try:
                    for i in range(1, steps + 1):
                        if self.stop_event.is_set():
                            pyautogui.mouseUp(button=button)
                            return False
                        while self.paused_event.is_set() and not self.stop_event.is_set():
                            time.sleep(0.05)
                        t = i / steps
                        cur_x = start_x + (x - start_x) * t
                        cur_y = start_y + (y - start_y) * t
                        pyautogui.moveTo(cur_x, cur_y, duration=0)
                        time.sleep(step_sleep)
                finally:
                    if not self.stop_event.is_set():
                        pyautogui.mouseUp(button=button)
            return True
        except Exception as e:
            print(f"拖拽出错: {e}")
            return False
    
    def wait(self, seconds=None, wait_type='time', target_image=None, target_window=None, 
             target_text=None, target_key=None, timeout=30, **kwargs):
        if wait_type == 'time' or wait_type is None:
            dur = seconds if seconds is not None else 1.0
            start_time = time.time()
            while time.time() - start_time < dur:
                if not self.running:
                    break
                time.sleep(0.01)
            return True
        
        start_time = time.time()
        
        if wait_type == 'image':
            if not target_image or not os.path.exists(target_image):
                print(f"等待图片: 图片路径无效 {target_image}")
                return False
            try:
                while time.time() - start_time < timeout:
                    if not self.running:
                        return False
                    try:
                        loc = pyautogui.locateOnScreen(target_image, confidence=0.8)
                        if loc:
                            print(f"等待图片: 已找到 {target_image}")
                            return True
                    except:
                        pass
                    time.sleep(0.5)
                print(f"等待图片: 超时 {timeout}秒")
                return False
            except Exception as e:
                print(f"等待图片出错: {e}")
                return False
        
        elif wait_type == 'window':
            keyword = target_window if target_window else ''
            try:
                import ctypes
                from ctypes import wintypes
                def _get_titles():
                    titles = []
                    def _cb(hwnd, _):
                        if ctypes.windll.user32.IsWindowVisible(hwnd):
                            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buf = ctypes.create_unicode_buffer(length + 1)
                                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                                titles.append(buf.value)
                        return True
                    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    ctypes.windll.user32.EnumWindows(EnumWindowsProc(_cb), 0)
                    return titles
                
                while time.time() - start_time < timeout:
                    if not self.running:
                        return False
                    try:
                        titles = _get_titles()
                        kw_lower = keyword.lower()
                        for t in titles:
                            if kw_lower in t.lower():
                                print(f"等待窗口: 已找到 '{keyword}'")
                                return True
                    except:
                        pass
                    time.sleep(0.5)
                print(f"等待窗口: 超时 {timeout}秒")
                return False
            except Exception as e:
                print(f"等待窗口出错: {e}")
                return False
        
        elif wait_type == 'clipboard':
            last_text = ''
            try:
                import pyperclip
                last_text = pyperclip.paste() or ''
            except:
                pass
            
            target = target_text if target_text else None
            while time.time() - start_time < timeout:
                if not self.running:
                    return False
                try:
                    import pyperclip
                    current = pyperclip.paste() or ''
                    if target:
                        if target in current:
                            print(f"等待剪贴板: 已包含 '{target}'")
                            return True
                    else:
                        if current.strip():
                            print(f"等待剪贴板: 已非空")
                            return True
                except:
                    pass
                time.sleep(0.3)
            print(f"等待剪贴板: 超时 {timeout}秒")
            return False
        
        elif wait_type == 'key':
            if not PYNPUT_AVAILABLE or not target_key:
                return False
            key_pressed = threading.Event()
            
            def on_key_press(key):
                try:
                    ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except:
                    ks = str(key).lower()
                if ks == target_key.lower():
                    key_pressed.set()
                    return False
                return True
            
            listener = keyboard.Listener(on_press=on_key_press)
            listener.start()
            
            while not key_pressed.is_set() and time.time() - start_time < timeout and self.running:
                time.sleep(0.05)
            
            listener.stop()
            if key_pressed.is_set():
                print(f"等待按键: 已按下 '{target_key}'")
                return True
            print(f"等待按键: 超时 {timeout}秒")
            return False
        
        return True
    
    def get_current_position(self):
        return pyautogui.position()
    
    def get_screen_size(self):
        return pyautogui.size()
    
    def hold_mouse(self, button='left', duration=1.0):
        try:
            if PYNPUT_AVAILABLE:
                btn = Button.left if button == 'left' else Button.right
                self.mouse_controller.press(btn)
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                self.mouse_controller.release(btn)
            else:
                pyautogui.mouseDown(button=button)
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                pyautogui.mouseUp(button=button)
            return True
        except Exception as e:
            print(f"长按鼠标出错: {e}")
            return False
    
    def hold_key(self, key, duration=1.0):
        try:
            if PYNPUT_AVAILABLE:
                key = self._map_key(key)
                
                self.keyboard_controller.press(key)
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                self.keyboard_controller.release(key)
            else:
                pyautogui.keyDown(key)
                start_time = time.time()
                while time.time() - start_time < duration:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)
                pyautogui.keyUp(key)
            return True
        except Exception as e:
            print(f"长按键盘按键出错: {e}")
            return False

    def fill_number(self, total_digits, start, end, prefix='', suffix='', interval=0.1):
        try:
            fixed_part_len = len(prefix) + len(suffix)
            if fixed_part_len >= total_digits:
                print(f"前缀+后缀长度({fixed_part_len})不能大于等于总位数({total_digits})")
                return False

            fill_digits = total_digits - fixed_part_len

            current_num = start
            progress_file = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AutoClicker', 'fill_progress.json')
            os.makedirs(os.path.dirname(progress_file), exist_ok=True)
            if self.gui_instance:
                progress = self.gui_instance._load_fill_progress(progress_file)
                if progress and progress.get('total_digits') == total_digits and progress.get('prefix') == prefix and progress.get('suffix') == suffix:
                    saved_end = progress.get('end', 0)
                    if saved_end >= end:
                        current_num = progress.get('next_value', start)
                    else:
                        saved_next = progress.get('next_value', start)
                        if saved_next <= end:
                            current_num = saved_next
                        else:
                            print(f"保存的next_value({saved_next})大于新end({end})，从start({start})开始")

            max_val = 10 ** fill_digits - 1
            if current_num > max_val:
                current_num = 0

            if current_num > end:
                current_num = start

            num_str = str(current_num).zfill(fill_digits)
            full_text = prefix + num_str + suffix


            self.type_text(full_text, interval=0.05)

            if interval > 0.05:
                wait_time = interval - 0.05
                start_time = time.time()
                while time.time() - start_time < wait_time:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.01)

            return {
                'total_digits': total_digits,
                'start': start,
                'end': end,
                'current_input': current_num,
                'next_value': current_num + 1 if current_num + 1 <= end else 0,
                'prefix': prefix,
                'suffix': suffix,
                'fill_digits': fill_digits
            }
        except Exception as e:
            print(f"填充数字出错: {e}")
            return False

    def open_file(self, filepath):
        try:
            os.startfile(filepath)
            return True
        except Exception as e:
            print(f"打开文件出错: {e}")
            return False

    def open_url(self, url):
        try:
            import webbrowser
            webbrowser.open(url, new=2)
            return True
        except Exception as e:
            print(f"打开网站出错: {e}")
            return False

    def _get_ocr_engine(self):
        if not OCR_AVAILABLE:
            return None
        if getattr(self, '_ocr_engine_obj', None) is not None:
            return self._ocr_engine_obj
        engine = None
        try:
            if OCR_BACKEND in ('rapidocr', 'rapidocr_onnxruntime'):
                engine = RapidOCR()
            elif OCR_BACKEND == 'pytesseract':
                engine = 'pytesseract'
        except Exception as e:
            print(f"OCR 引擎初始化失败: {e}")
            engine = None
        self._ocr_engine_obj = engine
        return engine

    def ocr_read(self, region=None, save_path=None, min_score=0.5, scale=1.0):
        if not OCR_AVAILABLE:
            msg = ("未安装 OCR 依赖，请运行 pip install rapidocr_onnxruntime "
                   "（或新版 pip install rapidocr）后重试")
            print(msg)
            return None

        region_tuple = None
        if region:
            try:
                parts = [float(p.strip()) for p in str(region).split(',')]
                if len(parts) == 4:
                    region_tuple = tuple(int(p) for p in parts)
                else:
                    print(f"OCR 区域格式错误（应为 x,y,w,h）: {region}，将按全屏识别")
            except Exception as e:
                print(f"OCR 区域解析失败: {e}，将按全屏识别")

        try:
            if region_tuple:
                img = pyautogui.screenshot(region=region_tuple)
            else:
                img = pyautogui.screenshot()
        except Exception as e:
            print(f"OCR 截屏失败: {e}")
            return None

        try:
            scale = float(scale)
            if scale <= 0:
                scale = 1.0
        except (TypeError, ValueError):
            scale = 1.0
        if scale != 1.0:
            from PIL import Image
            new_w = max(1, int(img.width * scale))
            new_h = max(1, int(img.height * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)
        img = img.convert('L')
        sx = 1.0 / scale if scale else 1.0
        try:
            import numpy as np
            img = np.array(img)
        except Exception:
            pass

        raw_results = []
        engine = self._get_ocr_engine()
        if engine is None:
            msg = ("未安装 OCR 依赖，请运行 pip install rapidocr_onnxruntime "
                   "（或新版 pip install rapidocr）后重试")
            print(msg)
            return None
        try:
            if OCR_BACKEND in ('rapidocr', 'rapidocr_onnxruntime'):
                raw = engine(img)
                if isinstance(raw, tuple):
                    raw = raw[0] if raw else None
                raw_results = raw if raw else []
            elif OCR_BACKEND == 'pytesseract':
                import pytesseract
                try:
                    from PIL import Image
                    if not isinstance(img, Image.Image):
                        img = Image.fromarray(img)
                except Exception as e:
                    print(f"OCR 图像转换失败: {e}")
                    return None
                data = pytesseract.image_to_data(img, lang='chi_sim+eng',
                                                 output_type=pytesseract.Output.DICT)
                n_blocks = len(data.get('text', []))
                for i in range(n_blocks):
                    text = str(data['text'][i]).strip()
                    if not text:
                        continue
                    try:
                        conf = float(data['conf'][i])
                    except (TypeError, ValueError):
                        conf = -1.0
                    if conf < 0:
                        continue
                    x = int(data['left'][i]); y = int(data['top'][i])
                    w = int(data['width'][i]); h = int(data['height'][i])
                    if w <= 0 or h <= 0:
                        continue
                    box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                    raw_results.append([box, text, conf / 100.0])
        except Exception as e:
            print(f"OCR 识别失败: {e}")
            return None

        region_off_x = region_tuple[0] if region_tuple else 0
        region_off_y = region_tuple[1] if region_tuple else 0
        results = []
        for item in raw_results:
            try:
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                box, text, score = item[0], str(item[1]), item[2]
                xs = [float(p[0]) * sx for p in box]
                ys = [float(p[1]) * sx for p in box]
                x = int(min(xs)) + region_off_x
                y = int(min(ys)) + region_off_y
                w = int(max(xs) - min(xs)); h = int(max(ys) - min(ys))
                score = float(score)
                if score < float(min_score):
                    continue
                results.append({
                    'text': text,
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'cx': int(x + w / 2),
                    'cy': int(y + h / 2),
                    'score': score,
                })
            except Exception:
                continue

        results = self._sort_ocr_results(results)

        self.vars['ocr_result'] = results
        self.vars['ocr_text'] = '\n'.join(r['text'] for r in results)

        print(f"[OCR] 识别到 {len(results)} 个文字块")
        for r in results:
            print(f"{r['text']} ({r['x']},{r['y']},{r['w']},{r['h']}) 置信度 {r['score']:.3f}")

        if save_path:
            try:
                save_dir = os.path.dirname(save_path)
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                if str(save_path).lower().endswith('.json'):
                    with open(save_path, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                else:
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(
                            f"{r['text']}\t{r['x']},{r['y']},{r['w']},{r['h']}\t"
                            f"中心({r['cx']},{r['cy']})\t置信度 {r['score']:.3f}"
                            for r in results))
                print(f"[OCR] 结果已保存到: {save_path}")
            except Exception as e:
                print(f"[OCR] 保存结果失败: {e}")

        return results

    @staticmethod
    def _sort_ocr_results(results):
        if not results:
            return results
        lines = []
        for r in sorted(results, key=lambda r: r['cy']):
            if not lines:
                lines.append([r])
                continue
            last_line = lines[-1]
            avg_cy = sum(x['cy'] for x in last_line) / len(last_line)
            avg_h = sum(x['h'] for x in last_line) / len(last_line)
            threshold = max(avg_h * 0.6, 8)
            if abs(r['cy'] - avg_cy) <= threshold:
                last_line.append(r)
            else:
                lines.append([r])
        sorted_results = []
        for line in lines:
            sorted_results.extend(sorted(line, key=lambda x: x['cx']))
        return sorted_results

    @staticmethod
    def _match_ocr_text(results, text, occurrence=1):
        if not results:
            return None
        target_text = str(text)
        matched = [r for r in results if r['text'] == target_text]
        if not matched:
            matched = [r for r in results if target_text in r['text']]
        if not matched:
            return None
        try:
            occ = int(occurrence)
        except (TypeError, ValueError):
            occ = 1
        if occ == -1:
            return matched[-1]
        if occ < 1:
            occ = 1
        if occ > len(matched):
            return matched[-1] if matched else None
        return matched[occ - 1]

    def ocr_click(self, text, occurrence=1, offset_x=0, offset_y=0,
                  region=None, min_score=0.5, on_fail='skip'):
        max_attempts = 3 if on_fail == 'retry' else 1
        for attempt in range(max_attempts):
            if not self.running:
                return False
            results = self.ocr_read(region=region, min_score=min_score)
            if results is None:
                if on_fail == 'error':
                    raise RuntimeError(f"OCR 文字定位失败: {text}（OCR 不可用）")
                print(f"OCR 文字定位: OCR 不可用，无法查找 {text}")
                return False
            target = self._match_ocr_text(results, text, occurrence)
            if target is not None:
                target_x = target['cx'] + int(offset_x)
                target_y = target['cy'] + int(offset_y)
                pyautogui.click(x=target_x, y=target_y, button='left', clicks=1, interval=0.1)
                print(f"OCR 文字定位: 已点击 '{text}' 位置({target_x}, {target_y}) 置信度 {target['score']:.3f}")
                return True
            print(f"OCR 文字定位: 未找到 '{text}' (尝试 {attempt + 1}/{max_attempts})")
            if on_fail == 'retry' and attempt < max_attempts - 1:
                time.sleep(0.5)
                continue
        if on_fail == 'error':
            raise RuntimeError(f"OCR 文字定位失败: 未找到文字 '{text}'")
        return False

    def add_action(self, action_type, **kwargs):
        if self.gui_instance:
            self.gui_instance._push_history(f"添加动作: {action_type}")
        action = {
            'type': action_type,
            'kwargs': kwargs,
            'timestamp': time.time(),
            'enabled': True
        }
        self.actions.append(action)
        return action
    
    def insert_action_at(self, index, action_type, **kwargs):
        if self.gui_instance:
            self.gui_instance._push_history(f"插入动作: {action_type}")
        action = {
            'type': action_type,
            'kwargs': kwargs,
            'timestamp': time.time(),
            'enabled': True
        }
        if index < 0:
            index = 0
        if index > len(self.actions):
            index = len(self.actions)
        self.actions.insert(index, action)
        return action
    
    def clear_actions(self):
        self.actions.clear()
    
    def save_actions(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.actions, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存出错: {e}")
            return False
    
    def load_actions(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                actions_data = json.load(f)
            normalized = []
            for item in (actions_data or []):
                if not isinstance(item, dict):
                    continue
                kw = item.get('kwargs')
                normalized.append({
                    'type': item.get('type', ''),
                    'kwargs': kw if isinstance(kw, dict) else {},
                    'timestamp': item.get('timestamp', time.time()),
                    'enabled': item.get('enabled', True),
                })
            with self._lock:
                self.actions = normalized
            return True
        except Exception as e:
            print(f"加载出错: {e}")
            return False
    
    def save_as_txt(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# 鼠标键盘自动化脚本\n")
                f.write("# 此文件由自动化工具生成，可以直接编辑\n")
                f.write("# 格式: 类型 参数=值\n")
                f.write("# 支持的动作类型: move, move_rel, locate_click, click, double_click, right_click, left_click, scroll, press, type, hotkey, drag, wait, hold, key_hold, multi_key, multi_mouse, multi_key_mouse, open_file, open_url\n")
                f.write("\n")
                
                for i, action in enumerate(self.actions):
                    action_type = action['type']
                    kwargs = action['kwargs']
                    
                    line = f"{action_type}"
                    for key, value in kwargs.items():
                        if isinstance(value, str):
                            if any(ch in value for ch in " \t\r\n'\"="):
                                line += f" {key}={value!r}"
                            else:
                                line += f" {key}='{value}'"
                        else:
                            line += f" {key}={value}"
                    f.write(line + "\n")
            return True
        except Exception as e:
            print(f"保存为文本文件出错: {e}")
            return False

    def _parse_txt_kwargs(self, rest):
        kwargs = {}
        i = 0
        n = len(rest)
        while i < n:
            while i < n and rest[i] in ' \t':
                i += 1
            if i >= n:
                break
            j = i
            while j < n and rest[j] not in ' \t=':
                j += 1
            key = rest[i:j]
            if not key or j >= n or rest[j] != '=':
                break
            i = j + 1
            if i < n and rest[i] in "'\"":
                quote = rest[i]
                i += 1
                chars = []
                while i < n:
                    ch = rest[i]
                    if ch == '\\' and i + 1 < n:
                        chars.append(ch + rest[i + 1])
                        i += 2
                        continue
                    if ch == quote:
                        i += 1
                        break
                    chars.append(ch)
                    i += 1
                raw = ''.join(chars)
                if '\\\\' in raw or "\\'" in raw or '\\"' in raw:
                    try:
                        kwargs[key] = _ast.literal_eval(quote + raw + quote)
                    except Exception:
                        kwargs[key] = raw
                else:
                    kwargs[key] = raw
            else:
                j = i
                while j < n and rest[j] not in ' \t':
                    j += 1
                value = rest[i:j]
                i = j
                try:
                    kwargs[key] = int(value)
                except ValueError:
                    try:
                        kwargs[key] = float(value)
                    except ValueError:
                        kwargs[key] = value
        return kwargs

    def load_from_txt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            actions = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(None, 1)
                if not parts:
                    continue

                action_type = parts[0]
                kwargs = self._parse_txt_kwargs(parts[1] if len(parts) > 1 else '')
                
                action = {
                    'type': action_type,
                    'kwargs': kwargs,
                    'timestamp': time.time(),
                    'enabled': True,
                }
                actions.append(action)
            
            with self._lock:
                self.actions = actions
            return True
        except Exception as e:
            print(f"从文本文件加载出错: {e}")
            return False
    
    def run_actions(self, repeat=1, interval=0):
        with self._lock:
            self.running = True
            self.current_action_index = 0
        
        self.stop_event.clear()
        
        with self._lock:
            actions_copy = list(self.actions)
        
        repeat_count = 0
        while True:
            if self.stop_event.is_set():
                break
            while self.paused_event.is_set() and not self.stop_event.is_set():
                time.sleep(0.05)
                
            for i, action in enumerate(actions_copy):
                if self.stop_event.is_set():
                    break
                    
                with self._lock:
                    self.current_action_index = i
                
                if not action.get('enabled', True):
                    if self.gui_instance:
                        self.gui_instance._log(f"跳过: [{i+1}] {action['type']} (已禁用)")
                    continue
                
                action_type = action['type']
                kwargs = action['kwargs']
                
                resolved_kwargs = self._resolve_kwargs(kwargs)
                
                if self.gui_instance:
                    self.gui_instance._log(f"执行: [{i+1}] {action_type}")
                    self.gui_instance._highlight_action(i)
                
                if action_type in self._action_mapping:
                    
                    if action_type == 'fill':
                        result = self._action_mapping[action_type](**resolved_kwargs)
                        if result and self.gui_instance:
                            self.gui_instance._save_fill_progress_from_result(result)
                    else:
                        self._action_mapping[action_type](**resolved_kwargs)
                    self._update_vars_after_action(action_type, resolved_kwargs)
                if interval > 0 and i < len(actions_copy) - 1:
                    if not self._wait_interruptible(interval):
                        break
            
            repeat_count += 1
            if repeat is not None and repeat_count >= repeat:
                break
            if interval > 0:
                if not self._wait_interruptible(interval):
                    break

        with self._lock:
            self.running = False
    
    def stop(self):
        with self._lock:
            self.running = False
        self.stop_event.set()
    
    def execute_loop(self, sub_actions=None, repeat=-1, interval=0.5):
        if sub_actions is None or not isinstance(sub_actions, list):
            return
        
        
        count = 0
        while True:
            if self.stop_event.is_set():
                break
            
            self.vars['loop_index'] = count
            for action in sub_actions:
                if self.stop_event.is_set():
                    return
                
                if not action.get('enabled', True):
                    continue
                
                action_type = action.get('type')
                kwargs = action.get('kwargs', {})
                
                resolved_kwargs = self._resolve_kwargs(kwargs)
                
                
                if action_type in self._action_mapping:
                    self._action_mapping[action_type](**resolved_kwargs)
                    self._update_vars_after_action(action_type, resolved_kwargs)
            
            count += 1
            if repeat > 0 and count >= repeat:
                break
            
            if interval > 0:
                if not self._wait_interruptible(interval):
                    return
    
    def execute_conditional(self, condition_type='keyboard', target_key=None, target_keys=None, 
                           target_x=None, target_y=None, duration=None, sub_actions=None, **kwargs):
        if sub_actions is None or not isinstance(sub_actions, list):
            return
        
        if target_keys is None:
            target_keys = [target_key] if target_key else []
        
        if condition_type == 'mouse':
            condition_type = 'click'
        
        
        if not PYNPUT_AVAILABLE:
            return
        
        triggered = threading.Event()
        
        def wait_for_trigger(listener):
            while listener.is_alive() and not self.stop_event.is_set() and not triggered.is_set():
                time.sleep(SLEEP_INTERVAL)
            listener.stop()
        
        if condition_type in ('keyboard', 'press'):
            def on_key_press(key):
                try:
                    key_str = None
                    if hasattr(key, 'char') and key.char:
                        key_str = key.char.lower()
                    elif hasattr(key, 'name') and key.name:
                        key_str = key.name.lower()
                    if key_str and key_str in [k.lower() for k in target_keys]:
                        triggered.set()
                        return False
                except:
                    pass
                return True
            
            listener = keyboard.Listener(on_press=on_key_press)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type in ('click', 'right_click', 'left_click'):
            def on_click(x, y, button, pressed):
                if pressed:
                    btn_name = str(button).split('.')[-1].lower() if '.' in str(button) else str(button).lower()
                    if btn_name in [k.lower() for k in target_keys]:
                        triggered.set()
                        return False
                return True
            
            listener = mouse.Listener(on_click=on_click)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'double_click':
            last_click = {'time': 0, 'button': None}
            
            def on_click(x, y, button, pressed):
                if pressed:
                    btn_name = str(button).split('.')[-1].lower() if '.' in str(button) else str(button).lower()
                    now = time.time()
                    match_btn = (not target_keys) or (btn_name == target_keys[0].lower())
                    if match_btn and last_click['button'] == btn_name and now - last_click['time'] < 0.4:
                        triggered.set()
                        return False
                    last_click['time'] = now
                    last_click['button'] = btn_name
                return True
            
            listener = mouse.Listener(on_click=on_click)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'scroll':
            direction = target_keys[0].lower() if target_keys else 'up'
            
            def on_scroll(x, y, dx, dy):
                if direction in ('up', 'down'):
                    if (direction == 'up' and dy > 0) or (direction == 'down' and dy < 0):
                        triggered.set()
                        return False
                elif direction in ('left', 'right'):
                    if (direction == 'right' and dx > 0) or (direction == 'left' and dx < 0):
                        triggered.set()
                        return False
                return True
            
            listener = mouse.Listener(on_scroll=on_scroll)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'move':
            target_px = target_x if target_x is not None else 0
            target_py = target_y if target_y is not None else 0
            threshold = 20
            
            def on_move(x, y):
                if abs(x - target_px) <= threshold and abs(y - target_py) <= threshold:
                    triggered.set()
                    return False
                return True
            
            listener = mouse.Listener(on_move=on_move)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'hold':
            hold_duration = duration if duration else 1.0
            press_time = {'time': 0, 'button': None}
            
            def on_click(x, y, button, pressed):
                btn_name = str(button).split('.')[-1].lower() if '.' in str(button) else str(button).lower()
                target_btn = target_keys[0].lower() if target_keys else 'left'
                if btn_name == target_btn:
                    if pressed:
                        press_time['time'] = time.time()
                        press_time['button'] = btn_name
                    else:
                        if press_time['time'] > 0 and time.time() - press_time['time'] >= hold_duration:
                            triggered.set()
                            return False
                        press_time['time'] = 0
                return True
            
            listener = mouse.Listener(on_click=on_click)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'key_hold':
            hold_duration = duration if duration else 1.0
            press_time = {'time': 0, 'key': None}
            
            def on_press(key):
                try:
                    key_str = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except:
                    key_str = str(key).lower()
                target_k = target_keys[0].lower() if target_keys else ''
                if key_str == target_k:
                    press_time['time'] = time.time()
                    press_time['key'] = key_str
            
            def on_release(key):
                if press_time['time'] > 0 and time.time() - press_time['time'] >= hold_duration:
                    triggered.set()
                    return False
                press_time['time'] = 0
                return True
            
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'hotkey':
            hotkey_str = target_keys[0] if target_keys else ''
            required_keys = [k.strip().lower() for k in hotkey_str.split('+') if k.strip()]
            pressed_keys = set()
            
            def on_press(key):
                try:
                    key_str = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except:
                    key_str = str(key).lower()
                pressed_keys.add(key_str)
                if all(rk in pressed_keys for rk in required_keys):
                    triggered.set()
                    return False
                return True
            
            def on_release(key):
                try:
                    key_str = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except:
                    key_str = str(key).lower()
                pressed_keys.discard(key_str)
                return True
            
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type == 'type':
            target_text = target_keys[0] if target_keys else ''
            last_clip = {'text': ''}
            try:
                import pyperclip
                last_clip['text'] = pyperclip.paste() or ''
            except:
                pass
            
            def check_clipboard_text():
                try:
                    import pyperclip
                    current = pyperclip.paste() or ''
                    if current != last_clip['text'] and target_text and target_text in current:
                        triggered.set()
                        return
                    last_clip['text'] = current
                except:
                    pass
            
            def poll_clipboard():
                while not triggered.is_set() and not self.stop_event.is_set():
                    check_clipboard_text()
                    time.sleep(self.clipboard_poll_interval)
            
            threading.Thread(target=poll_clipboard, daemon=True).start()
            while not triggered.is_set() and not self.stop_event.is_set():
                time.sleep(SLEEP_INTERVAL)
        
        elif condition_type == 'wait':
            wait_dur = duration if duration else 1.0
            if self._wait_interruptible(wait_dur):
                triggered.set()
        
        elif condition_type == 'fill':
            last_clip = {'text': ''}
            try:
                import pyperclip
                last_clip['text'] = pyperclip.paste() or ''
            except:
                pass
            
            def poll_clipboard_num():
                while not triggered.is_set() and not self.stop_event.is_set():
                    try:
                        import pyperclip
                        current = pyperclip.paste() or ''
                        if current != last_clip['text'] and current.strip().isdigit() and len(current.strip()) > 0:
                            triggered.set()
                            return
                        last_clip['text'] = current
                    except:
                        pass
                    time.sleep(self.clipboard_poll_interval)
            
            threading.Thread(target=poll_clipboard_num, daemon=True).start()
            while not triggered.is_set() and not self.stop_event.is_set():
                time.sleep(SLEEP_INTERVAL)
        
        elif condition_type == 'open_file_listen':
            monitor_path = target_keys[0] if target_keys else ''
            monitor_mode = kwargs.get('monitor_mode', 'exists')
            
            if not monitor_path:
                triggered.set()
            else:
                def poll_file():
                    last_mtime = {'time': 0}
                    if os.path.exists(monitor_path):
                        last_mtime['time'] = os.path.getmtime(monitor_path)
                        if monitor_mode == 'exists':
                            triggered.set()
                            return
                    
                    while not triggered.is_set() and not self.stop_event.is_set():
                        if os.path.exists(monitor_path):
                            if monitor_mode == 'exists':
                                triggered.set()
                                return
                            else:
                                curr_mtime = os.path.getmtime(monitor_path)
                                if curr_mtime != last_mtime['time']:
                                    triggered.set()
                                    return
                                last_mtime['time'] = curr_mtime
                        time.sleep(0.5)
                
                threading.Thread(target=poll_file, daemon=True).start()
                while not triggered.is_set() and not self.stop_event.is_set():
                    time.sleep(SLEEP_INTERVAL)
        
        elif condition_type == 'open_url_listen':
            url_keyword = target_keys[0] if target_keys else ''
            last_clip = {'text': ''}
            try:
                import pyperclip
                last_clip['text'] = pyperclip.paste() or ''
            except:
                pass
            
            def poll_clipboard_url():
                url_pattern = re.compile(r'https?://\S+')
                while not triggered.is_set() and not self.stop_event.is_set():
                    try:
                        import pyperclip
                        current = pyperclip.paste() or ''
                        if current != last_clip['text']:
                            urls = url_pattern.findall(current)
                            if url_keyword:
                                if any(url_keyword in url for url in urls):
                                    triggered.set()
                                    return
                            else:
                                if urls:
                                    triggered.set()
                                    return
                            last_clip['text'] = current
                    except:
                        pass
                    time.sleep(self.clipboard_poll_interval)
            
            threading.Thread(target=poll_clipboard_url, daemon=True).start()
            while not triggered.is_set() and not self.stop_event.is_set():
                time.sleep(SLEEP_INTERVAL)
        
        elif condition_type == 'browser_open':
            keyword = target_keys[0] if target_keys else ''
            if not keyword:
                triggered.set()
            else:
                import ctypes
                from ctypes import wintypes
                
                def _get_window_titles():
                    titles = []
                    def _enum_callback(hwnd, extra):
                        if ctypes.windll.user32.IsWindowVisible(hwnd):
                            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buffer = ctypes.create_unicode_buffer(length + 1)
                                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                                titles.append(buffer.value)
                        return True
                    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    ctypes.windll.user32.EnumWindows(EnumWindowsProc(_enum_callback), 0)
                    return titles
                
                def _poll_browser():
                    keyword_lower = keyword.lower()
                    while not triggered.is_set() and not self.stop_event.is_set():
                        try:
                            titles = _get_window_titles()
                            for title in titles:
                                if keyword_lower in title.lower():
                                    triggered.set()
                                    return
                        except:
                            pass
                        time.sleep(0.5)
                
                threading.Thread(target=_poll_browser, daemon=True).start()
                while not triggered.is_set() and not self.stop_event.is_set():
                    time.sleep(SLEEP_INTERVAL)
        
        elif condition_type == 'multi_key':
            hotkey_str = target_keys[0] if target_keys else ''
            required_keys = [k.strip().lower() for k in hotkey_str.split('+') if k.strip()]
            pressed_keys = set()
            
            def on_press(key):
                try:
                    key_str = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except:
                    key_str = str(key).lower()
                pressed_keys.add(key_str)
                if all(rk in pressed_keys for rk in required_keys):
                    triggered.set()
                    return False
                return True
            
            def on_release(key):
                try:
                    key_str = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except:
                    key_str = str(key).lower()
                pressed_keys.discard(key_str)
                return True
            
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            wait_for_trigger(listener)
        
        elif condition_type in ('multi_mouse', 'multi_key_mouse'):
            combo_str = target_keys[0] if target_keys else ''
            events = [e.strip().lower() for e in combo_str.split('+') if e.strip()]
            
            for event in events:
                if self.stop_event.is_set():
                    break
                event_triggered = threading.Event()
                
                if 'click' in event or 'left' in event or 'right' in event or 'middle' in event:
                    def on_combo_click(x, y, button, pressed, ev=event):
                        if pressed:
                            btn = str(button).split('.')[-1].lower()
                            if ev in (btn, f"{btn}_click"):
                                event_triggered.set()
                                return False
                        return True
                    listener = mouse.Listener(on_click=on_combo_click)
                elif 'scroll' in event:
                    def on_combo_scroll(x, y, dx, dy):
                        event_triggered.set()
                        return False
                    listener = mouse.Listener(on_scroll=on_combo_scroll)
                elif 'double' in event:
                    last_t = {'time': 0}
                    def on_combo_dbl(x, y, button, pressed):
                        if pressed:
                            now = time.time()
                            if now - last_t['time'] < 0.4:
                                event_triggered.set()
                                return False
                            last_t['time'] = now
                        return True
                    listener = mouse.Listener(on_click=on_combo_dbl)
                else:
                    def on_combo_key(key, ev=event):
                        try:
                            ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                        except:
                            ks = str(key).lower()
                        if ks == ev or ev in ks:
                            event_triggered.set()
                            return False
                        return True
                    listener = keyboard.Listener(on_press=on_combo_key)
                
                listener.start()
                while listener.is_alive() and not event_triggered.is_set() and not self.stop_event.is_set():
                    time.sleep(SLEEP_INTERVAL)
                listener.stop()
                
                if self.stop_event.is_set():
                    break
            
            if not self.stop_event.is_set():
                triggered.set()
        
        if triggered.is_set() and not self.stop_event.is_set():
            for action in sub_actions:
                if self.stop_event.is_set():
                    break
                
                if not action.get('enabled', True):
                    continue
                
                action_type = action.get('type')
                kwargs = action.get('kwargs', {})
                
                resolved_kwargs = self._resolve_kwargs(kwargs)
                
                if action_type in self._action_mapping:
                    self._action_mapping[action_type](**resolved_kwargs)
                    self._update_vars_after_action(action_type, resolved_kwargs)

class AutoClickerGUI:
    def __init__(self):
        self.autoclicker = AutoClicker()
        self.autoclicker.gui_instance = self
        self.window = tk.Tk()
        self.window.title("自动化脚本v1")
        
        self.screen_width = self.window.winfo_screenwidth()
        self.screen_height = self.window.winfo_screenheight()
        
        self.main_width = int(self.screen_width * 0.95)
        self.main_height = int(self.screen_height * 0.92)
        
        self.window.geometry(f"{self.main_width}x{self.main_height}")
        self.center_window(self.window, self.main_width, self.main_height)
        
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".window_pos")
        
        self.restore_window_position()
        
        self.recent_scripts = []
        self.recent_max = 10
        self.recent_config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".recent_scripts")
        self._recent_menu = None
        self._load_recent_scripts()
        
        self.position_cache = []
        
        self.highlight_progress_var = tk.BooleanVar(value=True)
        
        self.hotkey_start = tk.StringVar(value="f1")
        self.hotkey_position = tk.StringVar(value="f2")
        self.hotkey_pause = tk.StringVar(value="f3")
        
        self._undo_stack = []
        self._redo_stack = []
        self._max_history = 50
        self._recording_history = True
        
        self.tray_icon = None
        self.is_hidden = False
        
        self.listener = None
        self.hotkey_active = False
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.COLOR_PRIMARY = "#5B9BD5"
        self.COLOR_PRIMARY_HOVER = "#4A89C8"
        self.COLOR_PRIMARY_LIGHT = "#E8F4FD"
        self.COLOR_ACCENT = "#50C878"
        self.COLOR_ACCENT_HOVER = "#43B069"
        self.COLOR_DANGER = "#FF6B6B"
        self.COLOR_DANGER_HOVER = "#EE5A5A"
        self.COLOR_BG = "#F7F8FA"
        self.COLOR_CARD = "#FFFFFF"
        self.COLOR_CARD_ALT = "#F0F4F8"
        self.COLOR_BORDER = "#E2E8F0"
        self.COLOR_BORDER_LIGHT = "#EDF2F7"
        self.COLOR_TEXT = "#2D3748"
        self.COLOR_TEXT_SECONDARY = "#A0AEC0"
        self.COLOR_TEXT_MUTED = "#CBD5E0"
        self.COLOR_TEXT_ON_PRIMARY = "#FFFFFF"
        self.COLOR_TREE_SELECT = "#5B9BD5"
        self.COLOR_TREE_ROW_ALT = "#F7FAFC"
        self.COLOR_SCROLL_TROUGH = "#EDF2F7"
        self.COLOR_HOVER_BG = "#EEF4FB"
        self.COLOR_ACTIVE_BG = "#E2ECF6"
        self.COLOR_SUCCESS = "#50C878"
        self.COLOR_WARNING = "#FFB347"
        self.DARK_COLOR_BG = "#1A1A2E"
        self.DARK_COLOR_CARD = "#16213E"
        self.DARK_COLOR_CARD_ALT = "#1A2747"
        self.DARK_COLOR_TEXT = "#E2E8F0"
        self.DARK_COLOR_TEXT_SECONDARY = "#A0AEC0"
        self.DARK_COLOR_BORDER = "#2D3748"
        self.DARK_COLOR_PRIMARY = "#5B9BD5"
        self.DARK_COLOR_PRIMARY_HOVER = "#6BAFEF"
        self.DARK_COLOR_TREE_BG = "#16213E"
        self.DARK_COLOR_TREE_FG = "#E2E8F0"
        self.DARK_COLOR_TREE_SELECT = "#2B4C8C"
        self.DARK_COLOR_TREE_ALT = "#1A2747"
        self.DARK_COLOR_HOVER = "#1E3A5F"
        self.PAD_XS = 4
        self.PAD_SM = 8
        self.PAD_MD = 12
        self.PAD_LG = 20
        self.PAD_XL = 32
        self.FONT_NORMAL = ("Microsoft YaHei UI", 9)
        self.FONT_BOLD = ("Microsoft YaHei UI", 9, "bold")
        self.FONT_HEADING = ("Microsoft YaHei UI", 10, "bold")
        self.FONT_SMALL = ("Microsoft YaHei UI", 8)
        self.FONT_SMALL_BOLD = ("Microsoft YaHei UI", 8, "bold")
        self.ANIM_FAST = 80
        self.ANIM_NORMAL = 150
        self.ANIM_SLOW = 300
        self.HOVER_STEPS = 8
        self.ICON_PLAY = "\u25B6"
        self.ICON_STOP = "\u25A0"
        self.ICON_UP = "\u2B06"
        self.ICON_DOWN = "\u2B07"
        self.ICON_DELETE = "\u274C"
        self.ICON_EDIT = "\u270F"
        self.ICON_ADD = "\u2795"
        self.ICON_SAVE = "\uD83D\uDCBE"
        self.ICON_OPEN = "\uD83D\uDCC2"
        self.ICON_CLEAR = "\uD83D\uDDD1"
        self.ICON_LOOP = "\uD83D\uDD04"
        self.ICON_KEY = "\u2328"
        self.ICON_MOUSE = "\uD83D\uDDB1"
        self.ICON_MOVE = "\u2194"
        self.ICON_CLICK = "\uD83D\uDCA2"
        self.ICON_WAIT = "\u23F3"
        self.ICON_SCROLL_ARROW = "\u2195"
        self.ICON_CONDITIONAL = "\uD83D\uDEE1"
        self.ICON_FILL = "\uD83D\uDD22"
        self.ICON_SETTINGS = "\u2699"
        self.ICON_TRAY = "\uD83D\uDCBB"
        self.ICON_ARROW_RIGHT = "\u25B6"
        self.ICON_ARROW_LEFT = "\u25C0"
        self.ICON_CHECK = "\u2705"
        self.ICON_CLOSE = "\u274C"
        self.ICON_UP_ARROW = "\u2B06"
        self.ICON_DOWN_ARROW = "\u2B07"
        self.ICON_CONFIRM = "\u2705"
        self.ICON_CANCEL = "\u274C"
        self.ICON_CLIPBOARD = "\uD83D\uDCCB"
        self.ICON_SETTINGS_VS16 = "\u2699\uFE0F"
        self.ICON_SUN_VS16 = "\u2600\uFE0F"
        self.ICON_LIGHTNING = "\u26A1"
        self.ICON_PIN = "\uD83D\uDCCD"
        self.ICON_RED_CIRCLE = "\uD83D\uDD34"
        self.ICON_GREEN_CIRCLE = "\uD83D\uDFE2"
        self.ICON_MOON = "\uD83C\uDF19"
        self.dark_mode = False
        self.mouse_x = 0
        self.mouse_y = 0
        self._mouse_tracking = False

        style = ttk.Style()
        style.theme_use('clam')

        self.setup_ui()

        self.check_admin_privileges()
    
    def create_dialog(self, dialog):
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.attributes('-topmost', True)
        dialog.after(3000, lambda: dialog.attributes('-topmost', False))
    
    def center_window(self, window, width, height):
        x = (self.screen_width - width) // 2
        y = (self.screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_adaptive_dialog(self, title, width_ratio=0.5, height_ratio=0.6):
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        
        dialog_width = int(self.screen_width * width_ratio)
        dialog_height = int(self.screen_height * height_ratio)
        
        min_width = int(self.screen_width * 0.3)
        min_height = int(self.screen_height * 0.4)
        
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.minsize(min_width, min_height)
        dialog.resizable(True, True)
        
        self.center_window(dialog, dialog_width, dialog_height)
        
        self.create_dialog(dialog)
        
        return dialog, dialog_width, dialog_height
    
    def raise_window(self):
        self.window.lift()
        self.window.focus_force()
    
    def check_admin_privileges(self):
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("警告: 未以管理员身份运行，某些功能可能受限")
                print("建议: 右键点击程序 -> '以管理员身份运行'")
                return False
            else:
                print("[OK] 程序以管理员身份运行")
                return True
        except:
            print("无法检测管理员权限")
            return False
    
    def save_window_position(self):
        try:
            geom = self.window.geometry()
            with open(self.config_file, 'w') as f:
                f.write(geom)
        except Exception as e:
            print(f"保存窗口位置失败: {e}")
    
    def restore_window_position(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    geom = f.read().strip()
                if geom:
                    self.window.geometry(geom)
                    self.window.attributes('-topmost', True)
                    self.window.lift()
                    self.window.focus_force()
                    self.window.after(3000, lambda: self.window.attributes('-topmost', False))
        except Exception as e:
            print(f"恢复窗口位置失败: {e}")
    
    def setup_ui(self):
        self.window.columnconfigure(0, weight=0)
        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(0, weight=1)
        
        nav_frame = tk.Frame(self.window, width=180, relief='flat')
        nav_frame.grid(row=0, column=0, sticky='nsw')
        nav_frame.grid_propagate(False)
        nav_frame.configure(width=180)
        
        nav_title = ttk.Label(nav_frame, text="自动化脚本", 
                             font=self.FONT_HEADING)
        nav_title.pack(pady=(15, 5), padx=self.PAD_MD, anchor='w')
        
        nav_subtitle = ttk.Label(nav_frame, text="v2.0", 
                                  font=self.FONT_SMALL, 
                                  foreground=self.COLOR_TEXT_SECONDARY)
        nav_subtitle.pack(padx=self.PAD_MD, anchor='w')
        
        ttk.Separator(nav_frame, orient='horizontal').pack(fill='x', padx=self.PAD_MD, pady=self.PAD_SM)
        
        self.nav_buttons = []
        self.nav_indicators = []
        self.current_tab = 0
        
        nav_items = [
            ("动作序列", self.ICON_CLIPBOARD),
            ("设置与帮助", self.ICON_SETTINGS_VS16),
        ]
        
        for i, (name, icon) in enumerate(nav_items):
            btn_frame = ttk.Frame(nav_frame)
            btn_frame.pack(fill='x', padx=self.PAD_SM, pady=self.PAD_XS)
            
            indicator = tk.Frame(btn_frame, width=3, bg=self.COLOR_PRIMARY if i == 0 else self.COLOR_BG)
            indicator.pack(side='left', fill='y', padx=(0, 4))
            self.nav_indicators.append(indicator)
            
            btn = tk.Label(btn_frame, text=f" {icon}  {name}", 
                             font=self.FONT_NORMAL, anchor='w',
                             bg=self.COLOR_PRIMARY_LIGHT if i == 0 else self.COLOR_BG,
                             fg=self.COLOR_PRIMARY if i == 0 else self.COLOR_TEXT,
                             relief='flat')
            btn.pack(side='left', fill='x', expand=True, padx=self.PAD_XS, pady=self.PAD_XS)
            
            def make_fn(idx=i):
                def on_enter(e, btn=btn, idx=idx):
                    if idx != self.current_tab:
                        def fade_in(s=0):
                            if s >= self.HOVER_STEPS:
                                btn.configure(background=self.COLOR_HOVER_BG)
                                return
                            btn.after(self.ANIM_FAST // self.HOVER_STEPS, fade_in, s + 1)
                        fade_in()
                def on_leave(e, btn=btn, idx=idx):
                    if idx != self.current_tab:
                        btn.configure(background=self.COLOR_BG)
                    else:
                        btn.configure(background=self.COLOR_PRIMARY_LIGHT)
                btn.bind("<Enter>", on_enter)
                btn.bind("<Leave>", on_leave)
                btn.bind("<Button-1>", lambda e, i=idx: self._switch_tab(i))
            make_fn()
            
            self.nav_buttons.append(btn)
        
        ttk.Separator(nav_frame, orient='horizontal').pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        self.theme_btn_text = tk.StringVar(value=self.ICON_SUN_VS16 + " 亮色")
        self.theme_btn = ttk.Button(nav_frame, textvariable=self.theme_btn_text,
                                    command=self._toggle_dark_mode, style="Small.TButton")
        self.theme_btn.pack(padx=self.PAD_MD, pady=self.PAD_XS, fill='x')
        
        self.content_frame = ttk.Frame(self.window)
        self.content_frame.grid(row=0, column=1, sticky='nsew', padx=(0, 5), pady=self.PAD_XS)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=0)
        self.window.grid_columnconfigure(1, weight=1)
        
        self.tab_frames = []
        for _ in range(2):
            frame = ttk.Frame(self.content_frame)
            self.tab_frames.append(frame)
        
        self.tab_frames[0].pack(fill='both', expand=True)
        self._create_sequence_tab_body(self.tab_frames[0])
        self._create_settings_tab_body(self.tab_frames[1])
        
        self._create_status_bar()
        
        self.window.bind_all('<Control-z>', self.undo)
        self.window.bind_all('<Control-Z>', self.undo)
        self.window.bind_all('<Control-y>', self.redo)
        self.window.bind_all('<Control-Y>', self.redo)
        
        if PYSTRAY_AVAILABLE:
            self.create_tray_icon()
        
        self.start_hotkey_listener()
        
        self._start_mouse_tracking()
        
        self._open_dialogs = []
        self.window.bind_all('<Escape>', self._on_global_esc)

    def create_tray_icon(self):
        try:
            image = Image.new('RGB', (64, 64), color='white')
            dc = ImageDraw.Draw(image)
            dc.rectangle([16, 16, 48, 48], fill='blue')
            
            menu = (
                pystray.MenuItem("显示主窗口", self.show_window),
                pystray.MenuItem("开始执行", lambda: self.start_sequence()),
                pystray.MenuItem("停止执行", lambda: self.stop_sequence()),
                pystray.MenuItem("---", None),
                pystray.MenuItem("退出", self.quit_application)
            )
            
            self.tray_icon = pystray.Icon("auto_clicker", image, "自动化控制 v6.0", menu)
        except Exception as e:
            print(f"创建托盘图标失败: {e}")
    
    def _on_global_esc(self, event=None):
        toplevels = self.window.winfo_toplevel().winfo_children()
        for w in reversed(toplevels):
            if isinstance(w, tk.Toplevel) and w.winfo_exists():
                try:
                    w.destroy()
                    return 'break'
                except:
                    pass
        return 'break'
    
    def _apply_hotkey_settings(self):
        try:
            if hasattr(self, 'listener') and self.listener:
                self.listener.stop()
            
            self.start_hotkey_listener()
            messagebox.showinfo("成功", "热键设置已应用", parent=self.window)
        except Exception as e:
            messagebox.showerror("错误", f"应用热键失败: {e}", parent=self.window)
    
    def start_hotkey_listener(self):
        try:
            if PYNPUT_AVAILABLE:
                def on_press(key):
                    try:
                        key_name = key.name.lower() if hasattr(key, 'name') else str(key).lower()
                        start_hk = self.hotkey_start.get().lower()
                        pos_hk = self.hotkey_position.get().lower()
                        pause_hk = self.hotkey_pause.get().lower()
                        
                        if key_name == start_hk:
                            self.window.after(0, self.toggle_sequence)
                        elif key_name == pos_hk:
                            pos = self.autoclicker.get_current_position()
                            self.window.after(0, lambda: self.record_position(pos))
                        elif key_name == pause_hk:
                            self.window.after(0, self.toggle_pause)
                    except Exception as e:
                        print(f"热键处理出错: {e}")
                
                self.listener = keyboard.Listener(on_press=on_press)
                self.listener.start()
                self.hotkey_active = True
                print("[OK] 全局热键监听已启动 (F1: 开始/停止, F2: 获取并记录鼠标位置)")
            else:
                pass
        except Exception as e:
            print(f"启动热键监听失败: {e}")
    
    def record_position(self, pos):
        if len(self.position_cache) >= 10:
            self.position_cache.pop(0)
        
        position_info = {"x": pos.x, "y": pos.y, "time": time.strftime('%H:%M:%S')}
        self.position_cache.append(position_info)
        
        
        messagebox.showinfo("F2位置记录", f"已记录鼠标位置: X={pos.x}, Y={pos.y}\n总记录位置数: {len(self.position_cache)}", parent=self.window)
    
    def stop_hotkey_listener(self):
        try:
            if self.listener:
                self.listener.stop()
                self.hotkey_active = False
                print("全局热键监听已停止")
        except Exception as e:
            print(f"停止热键监听失败: {e}")
    
    def _create_sequence_tab_body(self, parent):
        outer_canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        outer_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=outer_canvas.yview)
        scrollable_frame = ttk.Frame(outer_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: outer_canvas.configure(scrollregion=outer_canvas.bbox("all"))
        )
        outer_window = outer_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def _on_outer_configure(event):
            outer_canvas.itemconfig(outer_window, width=event.width - 4)
        outer_canvas.bind("<Configure>", _on_outer_configure)
        outer_canvas.configure(yscrollcommand=outer_scrollbar.set)
        
        def _on_outer_mousewheel(event):
            outer_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        outer_canvas.bind("<Enter>", lambda e: outer_canvas.bind_all("<MouseWheel>", _on_outer_mousewheel))
        outer_canvas.bind("<Leave>", lambda e: outer_canvas.unbind_all("<MouseWheel>"))
        
        outer_canvas.pack(side="left", fill="both", expand=True)
        outer_scrollbar.pack(side="right", fill="y")
        
        seq_frame = ttk.Frame(scrollable_frame)
        seq_frame.pack(fill='x', expand=False)
        
        seq_frame.grid_rowconfigure(0, weight=3)
        seq_frame.grid_rowconfigure(1, weight=1)
        seq_frame.grid_rowconfigure(2, weight=0)
        seq_frame.grid_columnconfigure(0, weight=1)
        
        list_frame = ttk.LabelFrame(seq_frame, text="动作列表", padding=self.PAD_XS)
        list_frame.grid(row=0, column=0, sticky='nsew', padx=self.PAD_MD, pady=self.PAD_XS)
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        paned = ttk.PanedWindow(list_frame, orient='vertical')
        paned.grid(row=0, column=0, columnspan=2, sticky='nsew')
        
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=3)
        
        columns = ('序号', '状态', '类型', '参数', '时间')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        for col in columns:
            self.tree.heading(col, text=col)
        
        self.tree.column('序号', width=50, stretch=False)
        self.tree.column('状态', width=50, stretch=False, anchor='center')
        self.tree.column('类型', width=80, stretch=False)
        self.tree.column('参数', width=280, stretch=True)
        self.tree.column('时间', width=70, stretch=False)
        
        self.tree.pack(side='left', fill='both', expand=True)
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        h_scrollbar.pack(side='bottom', fill='x')
        self.tree.configure(yscrollcommand=v_scrollbar.set)
        self.tree.configure(xscrollcommand=h_scrollbar.set)
        
        self.tree.bind('<ButtonPress-1>', self._on_tree_press)
        self.tree.bind('<B1-Motion>', self._on_tree_drag)
        self.tree.bind('<ButtonRelease-1>', self._on_tree_release)
        self._drag_data = {'item': None, 'y_start': 0, 'moved': False}
        
        log_frame = ttk.LabelFrame(paned, text="执行日志", padding=2)
        paned.add(log_frame, weight=1)
        
        self.log_text = tk.Text(log_frame, height=4, wrap=tk.WORD, font=("Consolas", 9),
                               bg='#f5f5f5', fg='#333333')
        self.log_text.pack(fill='x', side='left', expand=True)
        
        log_scroll = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        log_scroll.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.configure(state='disabled')
        
        ttk.Button(log_frame, text="清空", width=6, 
                  command=self._clear_log).pack(side='right', padx=(2, 0))
        
        self.context_menu = tk.Menu(self.window, tearoff=0)
        
        insert_menu = tk.Menu(self.context_menu, tearoff=0)
        insert_menu.add_command(label="在上方插入移动指令", command=self.insert_move_above)
        insert_menu.add_command(label="在上方插入相对移动指令", command=self.insert_move_rel_above)
        insert_menu.add_command(label="在上方插入图像识别点击", command=self.insert_locate_click_above)
        insert_menu.add_command(label="在上方插入文字定位指令", command=self.insert_ocr_click_above)
        insert_menu.add_command(label="在上方插入左键点击", command=lambda: self.insert_click_above('left'))
        insert_menu.add_command(label="在上方插入右键点击", command=lambda: self.insert_click_above('right'))
        insert_menu.add_command(label="在上方插入双击", command=self.insert_double_click_above)
        insert_menu.add_command(label="在上方插入等待指令", command=self.insert_wait_above)
        insert_menu.add_command(label="在上方插入按键指令", command=self.insert_key_above)
        insert_menu.add_command(label="在上方插入输入文本", command=self.insert_type_above)
        insert_menu.add_command(label="在上方插入打开文件", command=self.insert_open_file_above)
        insert_menu.add_command(label="在上方插入打开网站", command=self.insert_open_url_above)
        insert_menu.add_command(label="在上方插入拖拽指令", command=self.insert_drag_above)
        insert_menu.add_command(label="在上方插入滚动指令", command=self.insert_scroll_above)
        insert_menu.add_command(label="在上方插入长按指令", command=self.insert_hold_above)
        insert_menu.add_command(label="在上方插入键盘长按指令", command=self.insert_key_hold_above)
        insert_menu.add_command(label="在上方插入多按键同步指令", command=self.insert_multi_key_above)
        insert_menu.add_command(label="在上方插入多鼠标按键同步指令", command=self.insert_multi_mouse_above)
        insert_menu.add_command(label="在上方插入键盘与鼠标同步指令", command=self.insert_multi_key_mouse_above)
        insert_menu.add_command(label="在上方插入填充数字指令", command=self.insert_fill_above)
        insert_menu.add_command(label="在上方插入循环触发指令", command=self.insert_loop_above)
        insert_menu.add_command(label="在上方插入条件控制指令", command=self.insert_conditional_above)
        self.context_menu.add_cascade(label="插入", menu=insert_menu)
        
        self.context_menu.add_command(label="启用/禁用", command=self.toggle_action_enabled)
        self.context_menu.add_command(label="复制动作", command=self.duplicate_action)
        
        move_menu = tk.Menu(self.context_menu, tearoff=0)
        move_menu.add_command(label="上移", command=lambda: self.move_action(-1))
        move_menu.add_command(label="下移", command=lambda: self.move_action(1))
        move_menu.add_command(label="移到顶部", command=lambda: self.move_action_to('top'))
        move_menu.add_command(label="移到底部", command=lambda: self.move_action_to('bottom'))
        self.context_menu.add_cascade(label="移动", menu=move_menu)
        
        self.context_menu.add_separator()
        
        batch_menu = tk.Menu(self.context_menu, tearoff=0)
        batch_menu.add_command(label="全选", command=self.select_all_actions)
        batch_menu.add_command(label="取消全选", command=self.deselect_all_actions)
        batch_menu.add_command(label="全部启用", command=self.enable_all_actions)
        batch_menu.add_command(label="全部禁用", command=self.disable_all_actions)
        self.context_menu.add_cascade(label="批量操作", menu=batch_menu)
        
        self.context_menu.add_separator()
        
        self.context_menu.add_command(label="删除选中", command=self.delete_selected_action)
        self.context_menu.add_command(label="清空所有", command=self.clear_action_list)
        
        self.context_menu.add_separator()
        
        self.context_menu.add_command(label="撤销 (Ctrl+Z)", command=self.undo)
        self.context_menu.add_command(label="重做 (Ctrl+Y)", command=self.redo)
        
        self.tree.bind("<Button-3>", self.show_context_menu)
        
        control_frame = ttk.LabelFrame(seq_frame, text="动作控制", padding=self.PAD_XS)
        control_frame.grid(row=1, column=0, sticky='nsew', padx=self.PAD_MD, pady=self.PAD_XS)
        control_frame.grid_rowconfigure(0, weight=1)
        control_frame.grid_columnconfigure(0, weight=1)
        
        control_canvas = tk.Canvas(control_frame, borderwidth=0, highlightthickness=0)
        control_scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=control_canvas.yview)
        button_frame = ttk.Frame(control_canvas)
        
        button_frame.bind(
            "<Configure>",
            lambda e: control_canvas.configure(scrollregion=control_canvas.bbox("all"))
        )
        
        canvas_window = control_canvas.create_window((0, 0), window=button_frame, anchor="nw")
        
        def _on_control_canvas_configure(event):
            control_canvas.itemconfig(canvas_window, width=event.width - 4)
        control_canvas.bind("<Configure>", _on_control_canvas_configure)
        
        control_canvas.configure(yscrollcommand=control_scrollbar.set)
        
        def _on_control_mousewheel(event):
            control_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        control_canvas.bind("<Enter>", lambda e: control_canvas.bind_all("<MouseWheel>", _on_control_mousewheel))
        control_canvas.bind("<Leave>", lambda e: control_canvas.unbind_all("<MouseWheel>"))
        
        control_canvas.grid(row=0, column=0, sticky="nsew")
        control_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.add_buttons_to_frame(button_frame)
        
        execute_frame = ttk.LabelFrame(seq_frame, text="执行控制", padding=self.PAD_MD)
        execute_frame.grid(row=2, column=0, sticky='ew', padx=self.PAD_MD, pady=self.PAD_XS)
        execute_frame.grid_columnconfigure(0, weight=1)
        
        exec_control_frame = ttk.Frame(execute_frame)
        exec_control_frame.pack(fill='x', pady=self.PAD_XS)
        exec_control_frame.grid_columnconfigure(0, weight=1)
        
        param_frame = ttk.Frame(exec_control_frame)
        param_frame.pack(side='left', fill='x', expand=True)
        
        ttk.Label(param_frame, text="重复次数:").pack(side='left')
        self.repeat_var = tk.StringVar(value="1")
        repeat_spin = ttk.Spinbox(param_frame, from_=1, to=999, 
                                 textvariable=self.repeat_var, width=5)
        repeat_spin.pack(side='left', padx=self.PAD_XS)
        
        self.infinite_loop_var = tk.BooleanVar(value=False)
        infinite_check = ttk.Checkbutton(param_frame, text="无限循环", 
                                         variable=self.infinite_loop_var)
        infinite_check.pack(side='left', padx=self.PAD_MD)
        
        ttk.Label(param_frame, text="动作间隔(秒):").pack(side='left', padx=self.PAD_MD)
        self.interval_var = tk.StringVar(value="0.5")
        interval_spin = ttk.Spinbox(param_frame, from_=0, to=10, 
                                   increment=0.1, textvariable=self.interval_var, width=5)
        interval_spin.pack(side='left', padx=self.PAD_XS)
        
        exec_btn_frame = ttk.Frame(exec_control_frame)
        exec_btn_frame.pack(side='right')
        self.pause_btn = ttk.Button(exec_btn_frame, text="暂停", 
                                   command=self.toggle_pause)
        self.pause_btn.pack(side='left', padx=self.PAD_XS)
        ttk.Button(exec_btn_frame, text="停止", 
                  command=self.stop_sequence).pack(side='left', padx=self.PAD_XS)
        self.start_btn = ttk.Button(exec_btn_frame, text="开始执行", 
                                    command=self.start_sequence)
        self.start_btn.pack(side='left', padx=self.PAD_XS)
        
        file_frame = ttk.Frame(execute_frame)
        file_frame.pack(fill='x', pady=self.PAD_XS)
        
        file_btns = [
            ("保存序列(.json)", self.save_sequence),
            ("加载序列(.json)", self.load_sequence),
            ("保存脚本(.txt)", self.save_script_txt),
            ("加载脚本(.txt)", self.load_script_txt),
            ("最近打开 ▾", None),
        ]
        
        file_inner = ttk.Frame(file_frame)
        file_inner.pack(fill='x')
        for c in range(len(file_btns)):
            file_inner.grid_columnconfigure(c, weight=1)
        for idx, (text, cmd) in enumerate(file_btns):
            btn = ttk.Button(file_inner, text=text, command=cmd)
            if text == "最近打开 ▾":
                btn.bind("<Button-1>", lambda e: self._show_recent_menu(btn))
            btn.grid(
                row=0, column=idx, padx=self.PAD_XS, pady=self.PAD_XS, sticky='ew')

        export_btn_frame = ttk.Frame(execute_frame)
        export_btn_frame.pack(fill='x', pady=self.PAD_XS)
        export_btn_frame.grid_columnconfigure(0, weight=1)
        export_btn_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Button(export_btn_frame, text="\U0001F4E6 导出为可执行文件(.exe)", 
                  command=self.export_to_exe).grid(row=0, column=0, padx=self.PAD_XS, sticky='ew')
        ttk.Button(export_btn_frame, text="\U0001F40D 导出为Python文件(.py)", 
                  command=self.export_to_python).grid(row=0, column=1, padx=self.PAD_XS, sticky='ew')

    def screenshot_select_region(self, save_path):
        import time
        self.window.withdraw()
        time.sleep(0.5)
        
        screen_w, screen_h = pyautogui.size()
        
        selector = tk.Toplevel()
        selector.attributes('-fullscreen', True)
        selector.attributes('-topmost', True)
        selector.overrideredirect(True)
        selector.configure(bg='black')
        
        from PIL import ImageTk
        full_img = pyautogui.screenshot()
        img_tk = ImageTk.PhotoImage(full_img)
        
        canvas = tk.Canvas(selector, highlightthickness=0, cursor='crosshair', 
                          bg='black', width=screen_w, height=screen_h)
        canvas.pack(fill='both', expand=True)
        
        bg_id = canvas.create_image(0, 0, anchor='nw', image=img_tk)
        canvas.image = img_tk
        
        overlay = canvas.create_rectangle(0, 0, screen_w, screen_h, 
                                          fill='black', stipple='gray50')
        
        hint = canvas.create_text(screen_w // 2, 40, 
                                 text='拖拽鼠标框选区域，松开完成截图，按 ESC 取消',
                                 fill='yellow', font=('Microsoft YaHei UI', 16, 'bold'))
        
        start_x = start_y = 0
        sel_rect = None
        result = {'region': None, 'cancelled': False}
        
        def on_press(event):
            nonlocal start_x, start_y, sel_rect
            pos = pyautogui.position()
            start_x, start_y = pos.x, pos.y
            sel_rect = canvas.create_rectangle(start_x, start_y, start_x, start_y,
                                               outline='red', width=3, fill='', stipple='')
        
        def on_drag(event):
            if sel_rect:
                pos = pyautogui.position()
                canvas.coords(sel_rect, start_x, start_y, pos.x, pos.y)
        
        def on_release(event):
            nonlocal result
            pos = pyautogui.position()
            end_x, end_y = pos.x, pos.y
            
            x1 = min(start_x, end_x)
            y1 = min(start_y, end_y)
            x2 = max(start_x, end_x)
            y2 = max(start_y, end_y)
            
            w = x2 - x1
            h = y2 - y1
            
            if w > 5 and h > 5:
                result['region'] = (x1, y1, w, h)
            selector.destroy()
        
        def on_esc(event=None):
            result['cancelled'] = True
            selector.destroy()
        
        selector.bind_all('<Button-1>', on_press)
        selector.bind_all('<B1-Motion>', on_drag)
        selector.bind_all('<ButtonRelease-1>', on_release)
        selector.bind_all('<Key-Escape>', on_esc)
        selector.bind_all('<KeyPress-Escape>', on_esc)
        selector.protocol("WM_DELETE_WINDOW", on_esc)
        
        selector.focus_force()
        selector.grab_set()
        
        self.window.wait_window(selector)
        
        self.window.deiconify()
        self.window.lift()
        
        if result['cancelled'] or not result['region']:
            return False
        
        region = result['region']
        try:
            cropped = pyautogui.screenshot(region=region)
            cropped.save(save_path)
            return True
        except Exception as e:
            print(f"截图保存失败: {e}")
            return False

    def _get_action_display_map(self):
        return {
            'move': '移动鼠标',
            'move_rel': '相对移动',
            'locate_click': '图像识别点击',
            'click': '左键点击',
            'double_click': '双击',
            'right_click': '右键点击',
            'wait': '等待',
            'press': '按键',
            'type': '输入文本',
            'scroll': '滚动',
            'drag': '拖拽',
            'hold': '长按',
            'key_hold': '键盘长按',
            'multi_key': '多按键同步',
            'multi_mouse': '多鼠标同步',
            'multi_key_mouse': '键盘鼠标同步',
            'fill': '填充数字',
            'loop': '循环控制',
            'conditional': '条件控制',
            'open_file': '打开文件',
            'open_url': '打开网站',
            'ocr_read': '屏幕文字识别',
            'ocr_click': '文字定位点击',
        }

    def create_action_button_frame(self, parent_frame, callback):
        action_categories = [
            ("基础操作", [
                ("移动鼠标", lambda: callback('move', self.add_move_action_sub)),
                ("相对移动", lambda: callback('move_rel', self.add_move_rel_action_sub)),
                ("图像识别点击", lambda: callback('locate_click', self.add_locate_click_action_sub)),
                ("左键点击", lambda: callback('click', self.add_click_action_sub)),
                ("右键点击", lambda: callback('right_click', self.add_right_click_action_sub)),
                ("双击", lambda: callback('double_click', self.add_double_click_action_sub)),
                ("等待", lambda: callback('wait', self.add_wait_action_sub)),
                ("按键", lambda: callback('press', self.add_key_action_sub)),
                ("输入文本", lambda: callback('type', self.add_type_action_sub)),
                ("打开文件", lambda: callback('open_file', self.add_open_file_action_sub)),
                ("打开网站", lambda: callback('open_url', self.add_open_url_action_sub)),
            ]),
            ("高级操作", [
                ("拖拽", lambda: callback('drag', self.add_drag_action_sub)),
                ("滚动", lambda: callback('scroll', self.add_scroll_action_sub)),
                ("长按", lambda: callback('hold', self.add_hold_action_sub)),
                ("键盘长按", lambda: callback('key_hold', self.add_key_hold_action_sub)),
                ("多按键同步", lambda: callback('multi_key', self.add_multi_key_action_sub)),
                ("多鼠标同步", lambda: callback('multi_mouse', self.add_multi_mouse_action_sub)),
                ("键盘鼠标同步", lambda: callback('multi_key_mouse', self.add_multi_key_mouse_action_sub)),
            ]),
            ("编辑操作", [
                ("填充数字", lambda: callback('fill', self.add_fill_action_sub)),
            ]),
        ]
        
        action_categories.append(
            ("特殊控制", [
                ("循环控制", lambda: callback('loop', self.add_loop_action_sub)),
                ("条件控制", lambda: callback('conditional', self.add_conditional_action_sub)),
            ])
        )
        
        search_frame = ttk.Frame(parent_frame)
        search_frame.pack(fill='x', padx=self.PAD_MD, pady=(self.PAD_SM, 0))
        
        self.action_search_var = tk.StringVar()
        self.action_search_var.trace_add('write', lambda *_: self._filter_action_buttons())
        search_entry = ttk.Entry(search_frame, textvariable=self.action_search_var, width=20)
        search_entry.pack(side='left')
        ttk.Label(search_frame, text=" 搜索按钮...", foreground='gray').pack(side='left')
        
        categories_frame = ttk.Frame(parent_frame)
        categories_frame.pack(fill='x', expand=False, padx=self.PAD_XS, pady=self.PAD_XS)
        
        for row, (category_name, actions) in enumerate(action_categories):
            categories_frame.rowconfigure(row, weight=0)
        categories_frame.columnconfigure(0, weight=1)
        
        for row, (category_name, actions) in enumerate(action_categories):
            category_frame = ttk.LabelFrame(categories_frame, text=category_name, padding=self.PAD_XS)
            category_frame.grid(row=row, column=0, sticky='ew', padx=self.PAD_XS, pady=self.PAD_XS)
            category_frame._btn_texts = []
            
            category_frame.grid_columnconfigure(0, weight=1)
            
            inner_frame = ttk.Frame(category_frame)
            inner_frame.pack(fill='x', expand=True, padx=self.PAD_XS, pady=self.PAD_XS)
            
            max_cols = max(3, min(7, len(actions)))
            for idx, (btn_text, btn_cmd) in enumerate(actions):
                category_frame._btn_texts.append(btn_text)
                row = idx // max_cols
                col = idx % max_cols
                btn = ttk.Button(inner_frame, text=btn_text, command=btn_cmd, padding=self.PAD_XS)
                btn.grid(row=row, column=col, sticky='ew', padx=self.PAD_XS, pady=self.PAD_XS)
            for c in range(max_cols):
                inner_frame.grid_columnconfigure(c, weight=1)
        
        self._action_category_frames = category_widgets_list if 'category_widgets_list' in dir() else []
        category_widgets_list = []
        for row, (category_name, actions) in enumerate(action_categories):
            category_widgets_list.append((categories_frame.grid_slaves(row=row, column=0)[0] if categories_frame.grid_slaves(row=row, column=0) else None, [categories_frame.grid_slaves(row=row, column=0)[0]] if categories_frame.grid_slaves(row=row, column=0) else []))
        self._action_category_frames = [(cf, [cf]) for cf in [categories_frame.grid_slaves(row=r, column=0)[0] for r in range(len(action_categories)) if categories_frame.grid_slaves(row=r, column=0)]]
    
    def _filter_action_buttons(self):
        keyword = self.action_search_var.get().strip().lower()
        if not hasattr(self, '_action_category_frames'):
            return
        
        for frame, btn_widgets in self._action_category_frames:
            if not keyword:
                for widget in btn_widgets:
                    if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                        widget.grid()
                continue
            
            has_match = any(keyword in text.lower() for text in frame._btn_texts)
            if has_match:
                for widget in btn_widgets:
                    widget.grid()
            else:
                for widget in btn_widgets:
                    widget.grid_remove()
    
    def add_buttons_to_frame(self, parent_frame):
        categories_frame = ttk.Frame(parent_frame)
        categories_frame.pack(fill='x', expand=False, padx=self.PAD_XS, pady=self.PAD_XS)
        
        categories_frame.columnconfigure(0, weight=1)
        
        categories = [
            ("基础操作", [
                ("添加移动", self.add_move_action, True),
                ("添加相对移动", self.add_move_rel_action, False),
                ("添加图像识别", self.add_locate_click_action, False),
                ("添加文字定位点击", self.add_ocr_click_action, False),
                ("添加左键点击", lambda: self.add_click_action('left'), False),
                ("添加右键点击", lambda: self.add_click_action('right'), False),
                ("添加双击", self.add_double_click_action, False),
                ("添加等待", self.add_wait_action, False),
                ("添加按键", self.add_key_action, False),
                ("添加输入文本", self.add_type_action, False),
                ("添加打开文件", self.add_open_file_action, False),
                ("添加打开网站", self.add_open_url_action, False),
            ]),
            ("高级操作", [
                ("添加拖拽", self.add_drag_action, False),
                ("添加滚动", self.add_scroll_action, False),
                ("添加长按", self.add_hold_action, False),
                ("添加键盘长按", self.add_key_hold_action, False),
                ("添加多按键同步", self.add_multi_key_action, False),
                ("添加多鼠标同步", self.add_multi_mouse_action, False),
                ("添加键盘鼠标同步", self.add_multi_key_mouse_action, False),
            ]),
            ("编辑操作", [
                ("删除选中", self.delete_selected_action, False),
                ("清空列表", self.clear_action_list, False),
                ("上移选中", self.move_up_action, False),
                ("下移选中", self.move_down_action, False),
            ]),
            ("特殊控制", [
                ("添加循环控制", self.add_loop_action, False),
                ("添加条件控制", self.add_conditional_action, False),
                ("添加填充数字", self.add_fill_action, False),
                ("屏幕文字识别", self.open_ocr_dialog, False),
            ]),
        ]
        
        categories_frame.grid_columnconfigure(0, weight=1)
        
        for row, (category_name, buttons) in enumerate(categories):
            categories_frame.grid_rowconfigure(row, weight=0)
            
            category_frame = ttk.LabelFrame(categories_frame, text=category_name, padding=self.PAD_XS)
            category_frame.grid(row=row, column=0, sticky='ew', padx=self.PAD_XS, pady=self.PAD_XS)
            
            category_frame.grid_columnconfigure(0, weight=1)
            
            inner_frame = ttk.Frame(category_frame)
            inner_frame.pack(fill='x', expand=True, padx=self.PAD_XS, pady=self.PAD_XS)
            MAX_COLS = 4
            for c in range(MAX_COLS):
                inner_frame.grid_columnconfigure(c, weight=1)
            
            col = 0
            row = 0
            for btn_text, btn_cmd, has_dropdown in buttons:
                if col >= MAX_COLS:
                    col = 0
                    row += 1
                if has_dropdown:
                    move_button_frame = ttk.Frame(inner_frame)
                    move_button_frame.grid(row=row, column=col, padx=self.PAD_XS, pady=self.PAD_XS, sticky='ew')
                    move_button_frame.grid_columnconfigure(0, weight=1)
                    
                    self.move_button = ttk.Button(move_button_frame, text=btn_text, 
                                                 command=btn_cmd, padding=self.PAD_XS)
                    self.move_button.grid(row=0, column=0, sticky='ew')
                    
                    self.move_dropdown = ttk.Button(move_button_frame, text="▼", width=2,
                                                   command=self.show_position_menu, padding=self.PAD_XS)
                    self.move_dropdown.grid(row=0, column=1)
                else:
                    btn = ttk.Button(inner_frame, text=btn_text, command=btn_cmd, padding=self.PAD_XS)
                    btn.grid(row=row, column=col, padx=self.PAD_XS, pady=self.PAD_XS, sticky='ew')
                col += 1
    
    def show_position_menu(self):
        if not self.position_cache:
            messagebox.showinfo("位置记录", "暂无F2记录的位置", parent=self.window)
            return
        
        temp_menu = tk.Menu(self.window, tearoff=0)
        
        for i, pos in enumerate(self.position_cache):
            label = f"位置{i+1}: ({pos['x']}, {pos['y']}) - {pos['time']}"
            temp_menu.add_command(
                label=label,
                command=lambda x=pos['x'], y=pos['y']: self.add_move_with_position(x, y)
            )
        
        temp_menu.add_separator()
        temp_menu.add_command(label="清除所有位置记录", command=self.clear_position_cache)
        
        try:
            temp_menu.tk_popup(self.move_dropdown.winfo_rootx(), 
                              self.move_dropdown.winfo_rooty() + self.move_dropdown.winfo_height())
        finally:
            temp_menu.grab_release()
    
    def add_move_with_position(self, x, y):
        duration = simpledialog.askfloat("移动时间", "移动时间(秒,0为瞬移):", 
                                       parent=self.window, initialvalue=0)
        if duration is None:
            duration = 0
        action = self.autoclicker.add_action('move', x=x, y=y, duration=duration)
        self.update_action_list()
    
    def clear_position_cache(self):
        self.position_cache.clear()
    
    def _create_settings_tab_body(self, parent):
        settings_frame = ttk.Frame(parent)
        settings_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(settings_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        scrollable_frame.bind("<Configure>", on_frame_configure)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        admin_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_LIGHTNING} 权限状态", padding=self.PAD_MD)
        admin_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if is_admin:
                status_text = f"{self.ICON_CHECK} 已获取管理员权限"
                status_color = self.COLOR_ACCENT
            else:
                status_text = f"{self.ICON_WARNING} 未获取管理员权限"
                status_color = self.COLOR_WARNING
        except:
            status_text = f"{self.ICON_WARNING} 无法检测管理员权限"
            status_color = self.COLOR_TEXT_SECONDARY
        
        admin_label = ttk.Label(admin_frame, text=status_text, foreground=status_color)
        admin_label.pack(anchor='w')
        
        if not is_admin:
            def request_admin():
                import sys
                import ctypes
                import os
                try:
                    self.save_window_position()
                    
                    script_path = os.path.abspath(sys.argv[0])
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", "pythonw.exe", f'"{script_path}"', None, 1)
                    self.window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"无法获取管理员权限: {e}", parent=self.window)
            
            ttk.Button(admin_frame, text="点击获取管理员权限", command=request_admin).pack(anchor='w', pady=self.PAD_XS)
        
        pos_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_PIN} 位置记录状态", padding=self.PAD_MD)
        pos_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        self.pos_status_label = ttk.Label(pos_frame, 
            text=f"{self.ICON_PIN} 已记录 {len(self.position_cache)} 个位置", 
            foreground=self.COLOR_PRIMARY)
        self.pos_status_label.pack(anchor='w')
        
        ttk.Button(pos_frame, text="查看位置记录", command=self.view_position_cache).pack(side='left', padx=self.PAD_XS)
        ttk.Button(pos_frame, text="清除位置记录", command=self.clear_position_cache).pack(side='left', padx=self.PAD_XS)
        
        background_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_TRAY} 后台控制", padding=self.PAD_MD)
        background_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        ttk.Button(background_frame, text=f"{self.ICON_TRAY} 最小化到系统托盘", 
                  command=self.minimize_to_tray).pack(side='left', padx=self.PAD_XS)
        ttk.Button(background_frame, text=f"{self.ICON_UP_ARROW} 显示/隐藏窗口", 
                  command=self.toggle_window_visibility).pack(side='left', padx=self.PAD_XS)
        
        hotkey_info_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_KEY} 热键说明", padding=self.PAD_MD)
        hotkey_info_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        hotkey_text = f"""{self.ICON_KEY} 全局热键（可在下方"全局热键设置"中自定义，后台也可触发）：
          开始/停止执行 — 默认 F1
          记录鼠标位置 — 默认 F2
          暂停/继续执行 — 默认 F3

        {self.ICON_LIGHTNING} 导出EXE快捷键（独立运行时）：
          F1  — 暂停 / 继续执行
          F2  — 停止并退出

        {self.ICON_LIGHTNING} 使用提示：
          1. 请以管理员身份运行，否则热键可能无效
          2. 部分安全软件可能拦截键盘钩子
          3. 全屏游戏请关闭"独占全屏"模式
          4. 图像识别功能需要安装 Pillow 库 (pip install Pillow)
          5. 变量系统支持在参数中输入 {{{{表达式}}}} 实现动态值
          6. 支持 Ctrl+Z 撤销 / Ctrl+Y 重做操作
          7. Treeview 支持拖拽排序、右键菜单批量操作
          8. 按 ESC 可关闭最顶层弹出窗口
        """
        
        hotkey_label = ttk.Label(hotkey_info_frame, text=hotkey_text, justify='left')
        hotkey_label.pack(anchor='w')
        
        features_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_CLIPBOARD} 功能说明", padding=self.PAD_MD)
        features_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        features_text = f"""{self.ICON_CLIPBOARD} 动作序列
          录制 / 编辑 / 保存 / 加载自动化操作序列
          支持导出独立 EXE 和 Python 文件

        {self.ICON_MOUSE} 鼠标操作
          绝对移动、相对移动、左键 / 右键点击、双击、拖拽、滚动、长按
          图像识别点击（截图选区 / 文件模板 / 置信度调节 / 失败重试）

        {self.ICON_KEY} 键盘操作
          单键 / 组合键 / 文本输入 / 键盘长按

        {self.ICON_LOOP} 高级控制
          多按键同步、键盘鼠标同步、循环控制、条件分支（支持多种监听机制）

        {self.ICON_PIN} 条件等待
          固定时长 / 等待图片出现 / 等待窗口出现 / 等待剪贴板 / 等待按键

        {self.ICON_FILL} 变量系统
          在参数中使用 {{{{表达式}}}} 引用动态变量
          内置变量: last_click_x/y, last_move_x/y, mouse_x/y, screen_w/h, loop_index
          支持运算: x={{{{last_click_x + 50}}}}, 随机: x={{{{random(100, 500)}}}}

        {self.ICON_CLIPBOARD} 编辑功能
          动作启用/禁用开关、拖拽排序、右键菜单分组操作
          Ctrl+Z 撤销 / Ctrl+Y 重做（最多50步历史）
          批量操作：全选、全部启用/禁用、移到顶部/底部

        {self.ICON_TRAY} 执行控制
          暂停/继续按钮、执行日志面板（可拖拽调整大小）、进度高亮可视化
          状态栏：实时鼠标坐标、执行耗时、禁用数量、撤销/重做计数

        {self.ICON_TRAY} 全局特性
          系统托盘后台运行、自定义全局热键（F1/F2/F3 可修改）
          管理员权限检测、导出独立 EXE / Python 文件
        """
        
        features_label = ttk.Label(features_frame, text=features_text, justify='left')
        features_label.pack(anchor='w')
        
        safety_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_LIGHTNING} 安全设置", padding=self.PAD_MD)
        safety_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        self.safety_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(safety_frame, text=f"{self.ICON_LIGHTNING} 启用故障安全功能（移动鼠标到屏幕左上角停止程序）", 
                       variable=self.safety_var, 
                       command=self.toggle_safety).pack(anchor='w')
        
        ttk.Label(safety_frame, 
                 text=f"{self.ICON_LIGHTNING} 启用后，快速移动鼠标至屏幕左上角 (0,0) 可紧急停止程序",
                 foreground=self.COLOR_TEXT_SECONDARY).pack(anchor='w', pady=self.PAD_XS)
        
        visual_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_MOUSE} 可视化设置", padding=self.PAD_MD)
        visual_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        ttk.Checkbutton(visual_frame, 
                       text=f"{self.ICON_MOUSE} 启用执行进度可视化（高亮当前执行的动作行）",
                       variable=self.highlight_progress_var).pack(anchor='w')
        
        ttk.Label(visual_frame, 
                 text=f"{self.ICON_MOUSE} 关闭后，执行时不再高亮 Treeview 中的当前动作",
                 foreground=self.COLOR_TEXT_SECONDARY).pack(anchor='w', pady=self.PAD_XS)
        
        hotkey_frame = ttk.LabelFrame(scrollable_frame, text=f"{self.ICON_KEY} 全局热键设置", padding=self.PAD_MD)
        hotkey_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
        
        ttk.Label(hotkey_frame, text=f'{self.ICON_KEY} 点击「选择按键」来自定义全局热键',
                 foreground=self.COLOR_TEXT_SECONDARY).pack(anchor='w', pady=(0, self.PAD_SM))
        
        hk1_row = ttk.Frame(hotkey_frame)
        hk1_row.pack(fill='x', pady=self.PAD_XS)
        ttk.Label(hk1_row, text="开始/停止执行:").pack(side='left')
        self.hk1_entry = ttk.Entry(hk1_row, textvariable=self.hotkey_start, width=15, state='readonly')
        self.hk1_entry.pack(side='left', padx=self.PAD_XS)
        ttk.Button(hk1_row, text="选择按键",
                  command=lambda: self.hotkey_start.set(self.select_key_dialog("选择开始/停止热键") or self.hotkey_start.get())).pack(side='left', padx=self.PAD_XS)
        
        hk2_row = ttk.Frame(hotkey_frame)
        hk2_row.pack(fill='x', pady=self.PAD_XS)
        ttk.Label(hk2_row, text="记录鼠标位置:").pack(side='left')
        self.hk2_entry = ttk.Entry(hk2_row, textvariable=self.hotkey_position, width=15, state='readonly')
        self.hk2_entry.pack(side='left', padx=self.PAD_XS)
        ttk.Button(hk2_row, text="选择按键",
                  command=lambda: self.hotkey_position.set(self.select_key_dialog("选择记录位置热键") or self.hotkey_position.get())).pack(side='left', padx=self.PAD_XS)
        
        hk3_row = ttk.Frame(hotkey_frame)
        hk3_row.pack(fill='x', pady=self.PAD_XS)
        ttk.Label(hk3_row, text="暂停/继续执行:").pack(side='left')
        self.hk3_entry = ttk.Entry(hk3_row, textvariable=self.hotkey_pause, width=15, state='readonly')
        self.hk3_entry.pack(side='left', padx=self.PAD_XS)
        ttk.Button(hk3_row, text="选择按键",
                  command=lambda: self.hotkey_pause.set(self.select_key_dialog("选择暂停/继续热键") or self.hotkey_pause.get())).pack(side='left', padx=self.PAD_XS)
        
        ttk.Button(hotkey_frame, text="应用热键设置", 
                  command=self._apply_hotkey_settings).pack(anchor='w', pady=(self.PAD_SM, 0))
        
        canvas.after(10, lambda: canvas.configure(scrollregion=canvas.bbox("all")))

    def view_position_cache(self):
        if not self.position_cache:
            messagebox.showinfo("位置记录", "暂无F2记录的位置", parent=self.window)
            return
        
        cache_window = tk.Toplevel(self.window)
        cache_window.title("F2记录的位置")
        cache_window.geometry("500x400")
        cache_window.resizable(True, True)
        cache_window.minsize(400, 300)
        self.create_dialog(cache_window)
        
        text_widget = tk.Text(cache_window, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(cache_window, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        for i, pos in enumerate(self.position_cache):
            text_widget.insert(tk.END, f"位置{i+1}: X={pos['x']}, Y={pos['y']} - 记录时间: {pos['time']}\n")
        
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def show_context_menu(self, event):
        try:
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"显示右键菜单出错: {e}")
    
    def get_selected_index(self):
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0])['values']
            index = int(item_values[0]) - 1
            return index
        return None

    def _add_or_insert_action(self, insert_index, action_type, **kwargs):
        if insert_index is not None:
            return self.autoclicker.insert_action_at(insert_index, action_type, **kwargs)
        else:
            return self.autoclicker.add_action(action_type, **kwargs)

    def _require_insert_index(self):
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作", parent=self.window)
            return None
        return index

    def insert_move_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_move_action(insert_index=index)

    def insert_move_rel_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_move_rel_action(insert_index=index)

    def insert_locate_click_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_locate_click_action(insert_index=index)

    def insert_ocr_click_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_ocr_click_action(insert_index=index)

    def insert_click_above(self, button_type='left'):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_click_action(button_type=button_type, insert_index=index)

    def insert_double_click_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_double_click_action(insert_index=index)

    def insert_wait_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_wait_action(insert_index=index)

    def insert_key_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_key_action(insert_index=index)

    def insert_type_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_type_action(insert_index=index)

    def insert_open_file_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_open_file_action(insert_index=index)

    def insert_open_url_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_open_url_action(insert_index=index)

    def insert_drag_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_drag_action(insert_index=index)

    def insert_scroll_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_scroll_action(insert_index=index)

    def insert_hold_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_hold_action(insert_index=index)

    def insert_key_hold_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_key_hold_action(insert_index=index)

    def insert_multi_key_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_multi_key_action(insert_index=index)

    def insert_multi_mouse_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_multi_mouse_action(insert_index=index)

    def insert_multi_key_mouse_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_multi_key_mouse_action(insert_index=index)

    def insert_fill_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_fill_action(insert_index=index)

    def insert_loop_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_loop_action(insert_index=index)

    def insert_conditional_above(self):
        index = self._require_insert_index()
        if index is None:
            return
        self.add_conditional_action(insert_index=index)

    def select_key_dialog(self, title="选择按键"):
        dialog, dialog_width, dialog_height = self.create_adaptive_dialog(title, 0.5, 0.45)
        
        categories = {
            "字母": [chr(i) for i in range(ord('a'), ord('z')+1)],
            "数字": [str(i) for i in range(0, 10)],
            "功能键": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            "控制键": ["space", "enter", "tab", "esc", "backspace", "delete", "shift", "ctrl", "alt", "caps_lock", "cmd"],
            "导航键": ["home", "end", "page_up", "page_down", "insert", "menu", "up", "down", "left", "right"],
            "其他": ["print_screen", "scroll_lock", "pause", "num_lock"]
        }
        
        selected_key = tk.StringVar()
        
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True)
        
        for category, keys in categories.items():
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=category)
            
            if category == "字母":
                for i, key in enumerate(keys):
                    row = i // 13
                    col = i % 13
                    btn = ttk.Button(frame, text=key, 
                                   command=lambda k=key: [selected_key.set(k), dialog.destroy()])
                    btn.grid(row=row, column=col, sticky='nsew')
                for col in range(13):
                    frame.grid_columnconfigure(col, weight=1, uniform='letter_col')
                for row in range(2):
                    frame.grid_rowconfigure(row, weight=1, uniform='letter_row')
                    
            elif category == "数字":
                for i, key in enumerate(keys):
                    btn = ttk.Button(frame, text=key, 
                                   command=lambda k=key: [selected_key.set(k), dialog.destroy()])
                    btn.grid(row=0, column=i, sticky='nsew')
                for col in range(10):
                    frame.grid_columnconfigure(col, weight=1, uniform='num_col')
                frame.grid_rowconfigure(0, weight=1)
                    
            elif category == "功能键":
                for i, key in enumerate(keys):
                    row = i // 6
                    col = i % 6
                    btn = ttk.Button(frame, text=key, 
                                   command=lambda k=key: [selected_key.set(k), dialog.destroy()])
                    btn.grid(row=row, column=col, sticky='nsew')
                for col in range(6):
                    frame.grid_columnconfigure(col, weight=1, uniform='func_col')
                for row in range(2):
                    frame.grid_rowconfigure(row, weight=1, uniform='func_row')
                    
            else:
                num_keys = len(keys)
                if num_keys <= 5:
                    cols = 5
                    rows = 1
                elif num_keys <= 10:
                    cols = 5
                    rows = 2
                else:
                    cols = 5
                    rows = 3
                
                for i, key in enumerate(keys):
                    row = i // cols
                    col = i % cols
                    btn = ttk.Button(frame, text=key, 
                                   command=lambda k=key: [selected_key.set(k), dialog.destroy()])
                    btn.grid(row=row, column=col, sticky='nsew')
                for col in range(cols):
                    frame.grid_columnconfigure(col, weight=1, uniform='other_col')
                for row in range(rows):
                    frame.grid_rowconfigure(row, weight=1, uniform='other_row')
        
        custom_frame = ttk.Frame(dialog)
        custom_frame.pack(fill='x', padx=self.PAD_XS, pady=self.PAD_XS)
        
        ttk.Label(custom_frame, text="或输入自定义按键:").pack(side='left', padx=self.PAD_XS)
        custom_entry = ttk.Entry(custom_frame)
        custom_entry.pack(side='left', padx=self.PAD_XS, fill='x', expand=True)
        
        def use_custom_key():
            custom_value = custom_entry.get().strip()
            if custom_value:
                selected_key.set(custom_value)
                dialog.destroy()
        
        ttk.Button(custom_frame, text="使用自定义", command=use_custom_key).pack(side='left', padx=self.PAD_XS)
        
        self.window.wait_window(dialog)
        
        return selected_key.get()
    
    def select_multi_keys_dialog(self, title="选择按键"):
        dialog, dialog_width, dialog_height = self.create_adaptive_dialog(title, 0.5, 0.45)
        
        categories = {
            "字母": [chr(i) for i in range(ord('a'), ord('z')+1)],
            "数字": [str(i) for i in range(0, 10)],
            "功能键": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            "控制键": ["space", "enter", "tab", "esc", "backspace", "delete", "shift", "ctrl", "alt", "caps_lock", "cmd"],
            "导航键": ["home", "end", "page_up", "page_down", "insert", "menu", "up", "down", "left", "right"],
            "其他": ["print_screen", "scroll_lock", "pause", "num_lock"]
        }
        
        selected_keys = []
        button_refs = {}
        
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True)
        
        style = ttk.Style()
        style.configure('Selected.TButton', background=self.COLOR_PRIMARY, foreground=self.COLOR_CARD)
        
        for category, keys in categories.items():
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=category)
            
            if category == "字母":
                for i, key in enumerate(keys):
                    row = i // 13
                    col = i % 13
                    
                    def make_callback(k):
                        def callback():
                            if k in selected_keys:
                                selected_keys.remove(k)
                                button_refs[k].config(style='TButton')
                            else:
                                selected_keys.append(k)
                                button_refs[k].config(style='Selected.TButton')
                        return callback
                    
                    btn = ttk.Button(frame, text=key, command=make_callback(key))
                    button_refs[key] = btn
                    btn.grid(row=row, column=col, sticky='nsew')
                for col in range(13):
                    frame.grid_columnconfigure(col, weight=1, uniform='letter_col')
                for row in range(2):
                    frame.grid_rowconfigure(row, weight=1, uniform='letter_row')
                    
            elif category == "数字":
                for i, key in enumerate(keys):
                    def make_callback(k):
                        def callback():
                            if k in selected_keys:
                                selected_keys.remove(k)
                                button_refs[k].config(style='TButton')
                            else:
                                selected_keys.append(k)
                                button_refs[k].config(style='Selected.TButton')
                        return callback
                    
                    btn = ttk.Button(frame, text=key, command=make_callback(key))
                    button_refs[key] = btn
                    btn.grid(row=0, column=i, sticky='nsew')
                for col in range(10):
                    frame.grid_columnconfigure(col, weight=1, uniform='num_col')
                frame.grid_rowconfigure(0, weight=1)
                    
            elif category == "功能键":
                for i, key in enumerate(keys):
                    row = i // 6
                    col = i % 6
                    
                    def make_callback(k):
                        def callback():
                            if k in selected_keys:
                                selected_keys.remove(k)
                                button_refs[k].config(style='TButton')
                            else:
                                selected_keys.append(k)
                                button_refs[k].config(style='Selected.TButton')
                        return callback
                    
                    btn = ttk.Button(frame, text=key, command=make_callback(key))
                    button_refs[key] = btn
                    btn.grid(row=row, column=col, sticky='nsew')
                for col in range(6):
                    frame.grid_columnconfigure(col, weight=1, uniform='func_col')
                for row in range(2):
                    frame.grid_rowconfigure(row, weight=1, uniform='func_row')
                    
            else:
                num_keys = len(keys)
                if num_keys <= 5:
                    cols = 5
                    rows = 1
                elif num_keys <= 10:
                    cols = 5
                    rows = 2
                else:
                    cols = 5
                    rows = 3
                
                for i, key in enumerate(keys):
                    row = i // cols
                    col = i % cols
                    
                    def make_callback(k):
                        def callback():
                            if k in selected_keys:
                                selected_keys.remove(k)
                                button_refs[k].config(style='TButton')
                            else:
                                selected_keys.append(k)
                                button_refs[k].config(style='Selected.TButton')
                        return callback
                    
                    btn = ttk.Button(frame, text=key, command=make_callback(key))
                    button_refs[key] = btn
                    btn.grid(row=row, column=col, sticky='nsew')
                for col in range(cols):
                    frame.grid_columnconfigure(col, weight=1, uniform='other_col')
                for row in range(rows):
                    frame.grid_rowconfigure(row, weight=1, uniform='other_row')
        
        custom_frame = ttk.Frame(dialog)
        custom_frame.pack(fill='x', padx=self.PAD_XS, pady=self.PAD_XS)
        
        ttk.Label(custom_frame, text="或输入自定义按键:").pack(side='left', padx=self.PAD_XS)
        custom_entry = ttk.Entry(custom_frame)
        custom_entry.pack(side='left', padx=self.PAD_XS, fill='x', expand=True)
        
        def use_custom_key():
            custom_value = custom_entry.get().strip()
            if custom_value and custom_value not in selected_keys:
                selected_keys.append(custom_value)
                custom_entry.delete(0, tk.END)
        
        ttk.Button(custom_frame, text="添加自定义", command=use_custom_key).pack(side='left', padx=self.PAD_XS)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=self.PAD_XS, pady=self.PAD_XS)
        ttk.Button(btn_frame, text="确定", command=dialog.destroy).pack(side='right', padx=self.PAD_XS)
        
        self.window.wait_window(dialog)
        
        return selected_keys
    
    def get_current_pos(self):
        pos = self.autoclicker.get_current_position()
        messagebox.showinfo("当前位置", f"当前鼠标位置: X={pos.x}, Y={pos.y}", parent=self.window)
    
    def move_to_pos(self):
        pass
    
    def type_text(self):
        pass
    
    def add_move_action(self, insert_index=None):
        try:
            dialog = tk.Toplevel(self.window)
            dialog.title("添加移动")
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.resizable(False, False)

            main = ttk.Frame(dialog, padding=15)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text="鼠标移动", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

            ttk.Label(main, text="坐标类型: 屏幕坐标（相对屏幕左上角）", foreground='#0078D4',
                      font=("Microsoft YaHei UI", 9, "italic")).pack(anchor='w', pady=(0, 8))

            coord_frame = ttk.Frame(main)
            coord_frame.pack(fill='x', pady=5)
            ttk.Label(coord_frame, text="X 坐标:").grid(row=0, column=0, sticky='w', padx=(0, 5))
            x_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=x_var, width=10).grid(row=0, column=1, padx=(0, 15))
            ttk.Label(coord_frame, text="Y 坐标:").grid(row=0, column=2, sticky='w', padx=(0, 5))
            y_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=y_var, width=10).grid(row=0, column=3)

            btn_row = ttk.Frame(main)
            btn_row.pack(fill='x', pady=5)
            def get_pos():
                pos = self.autoclicker.get_current_position()
                x_var.set(pos.x)
                y_var.set(pos.y)
            ttk.Button(btn_row, text="获取当前鼠标位置 (F2)", command=get_pos).pack(side='left', padx=(0, 10))

            if self.position_cache:
                cache_items = [f"[{p['time']}] X={p['x']}, Y={p['y']}" for p in self.position_cache]
                cache_var = tk.StringVar(value="")
                def on_cache_select(*args):
                    sel = cache_combo.current()
                    if sel >= 0:
                        p = self.position_cache[sel]
                        x_var.set(p['x'])
                        y_var.set(p['y'])
                ttk.Label(btn_row, text="F2记录:").pack(side='left')
                cache_combo = ttk.Combobox(btn_row, values=cache_items, width=22, state="readonly")
                cache_combo.pack(side='left', padx=(5, 0))
                cache_combo.bind("<<ComboboxSelected>>", on_cache_select)

            dur_frame = ttk.Frame(main)
            dur_frame.pack(fill='x', pady=5)
            ttk.Label(dur_frame, text="移动时间(秒, 0=瞬移):").pack(side='left')
            dur_var = tk.StringVar(value="0")
            ttk.Entry(dur_frame, textvariable=dur_var, width=8).pack(side='left', padx=(5, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            def on_cancel():
                dialog.destroy()

            act_btn = ttk.Frame(main)
            act_btn.pack(fill='x', pady=(10, 0))
            ttk.Button(act_btn, text="确定", command=on_ok).pack(side='right', padx=5)
            ttk.Button(act_btn, text="取消", command=on_cancel).pack(side='right')

            self.window.wait_window(dialog)
            if not result['ok']:
                return

            self._add_or_insert_action(insert_index, 'move', x=x_var.get(), y=y_var.get(),
                                       duration=float(dur_var.get()))
            self.update_action_list()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字", parent=self.window)
    
    def add_click_action(self, button_type='left', insert_index=None):
        action = self._add_or_insert_action(insert_index, 'click', button=button_type, clicks=1)
        self.update_action_list()
        button_name = "左键" if button_type == 'left' else "右键"
    
    def add_double_click_action(self, insert_index=None):
        action = self._add_or_insert_action(insert_index, 'click', button='left', clicks=2)
        self.update_action_list()
    
    def add_move_rel_action(self, insert_index=None):
        try:
            dialog = tk.Toplevel(self.window)
            dialog.title("相对移动")
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.resizable(False, False)

            main = ttk.Frame(dialog, padding=15)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text="相对移动", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

            coord_frame = ttk.Frame(main)
            coord_frame.pack(fill='x', pady=5)
            ttk.Label(coord_frame, text="水平位移(dx):").grid(row=0, column=0, sticky='w', padx=(0, 5))
            dx_var = tk.IntVar(value=100)
            ttk.Entry(coord_frame, textvariable=dx_var, width=10).grid(row=0, column=1, padx=(0, 15))
            ttk.Label(coord_frame, text="垂直位移(dy):").grid(row=0, column=2, sticky='w', padx=(0, 5))
            dy_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=dy_var, width=10).grid(row=0, column=3)

            dur_frame = ttk.Frame(main)
            dur_frame.pack(fill='x', pady=5)
            ttk.Label(dur_frame, text="移动时间(秒, 0=瞬移):").pack(side='left')
            dur_var = tk.StringVar(value="0")
            ttk.Entry(dur_frame, textvariable=dur_var, width=8).pack(side='left', padx=(5, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            ttk.Button(main, text="确定", command=on_ok).pack(side='right', padx=5, pady=(10, 0))
            ttk.Button(main, text="取消", command=lambda: dialog.destroy()).pack(side='right', pady=(10, 0))

            self.window.wait_window(dialog)
            if not result['ok']:
                return
            self._add_or_insert_action(insert_index, 'move_rel', dx=dx_var.get(), dy=dy_var.get(),
                                       duration=float(dur_var.get()))
            self.update_action_list()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字", parent=self.window)
    
    def add_locate_click_action(self, insert_index=None):
        dialog = tk.Toplevel(self.window)
        dialog.title("图像识别点击")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(400, 300)
        
        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)
        
        ttk.Label(main, text="图像识别点击", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))
        
        img_frame = ttk.LabelFrame(main, text="模板图片", padding=10)
        img_frame.pack(fill='x', pady=5)
        
        img_var = tk.StringVar(value="")
        img_row = ttk.Frame(img_frame)
        img_row.pack(fill='x')
        ttk.Entry(img_row, textvariable=img_var, width=30).pack(side='left')
        
        def browse_img():
            fp = filedialog.askopenfilename(title="选择模板图片",
                filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")],
                parent=dialog)
            if fp:
                img_var.set(fp)
        
        def capture_region():
            import os
            capture_dir = r"C:\Users\ljw\Pictures"
            os.makedirs(capture_dir, exist_ok=True)
            tmp_path = os.path.join(capture_dir, "autoclicker_capture.png")
            if self.screenshot_select_region(tmp_path):
                img_var.set(tmp_path)
                messagebox.showinfo("截图成功", f"已保存到: {tmp_path}", parent=dialog)
        
        ttk.Button(img_row, text="浏览", command=browse_img).pack(side='left', padx=5)
        ttk.Button(img_row, text="截图选区", command=capture_region).pack(side='left')
        
        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)
        
        ttk.Label(param_frame, text="置信度(0.5-1.0):").grid(row=0, column=0, sticky='w')
        conf_var = tk.DoubleVar(value=0.9)
        ttk.Spinbox(param_frame, from_=0.5, to=1.0, increment=0.05, textvariable=conf_var, width=8).grid(row=0, column=1, sticky='w')
        
        ttk.Label(param_frame, text="点击偏移X:").grid(row=1, column=0, sticky='w')
        offx_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offx_var, width=8).grid(row=1, column=1, sticky='w')
        
        ttk.Label(param_frame, text="点击偏移Y:").grid(row=2, column=0, sticky='w')
        offy_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offy_var, width=8).grid(row=2, column=1, sticky='w')
        
        ttk.Label(param_frame, text="鼠标按钮:").grid(row=3, column=0, sticky='w')
        btn_var = tk.StringVar(value="left")
        ttk.Combobox(param_frame, values=["left", "right", "middle"], textvariable=btn_var, width=10, state="readonly").grid(row=3, column=1, sticky='w')
        
        ttk.Label(param_frame, text="失败处理:").grid(row=4, column=0, sticky='w')
        fail_var = tk.StringVar(value="跳过")
        ttk.Combobox(param_frame, values=["跳过", "重试3次", "报错"], textvariable=fail_var, width=10, state="readonly").grid(row=4, column=1, sticky='w')
        
        result = {'ok': False}
        def on_ok():
            if not img_var.get():
                messagebox.showerror("错误", "请选择模板图片", parent=dialog)
                return
            result['ok'] = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right')
        
        self.window.wait_window(dialog)
        
        if not result['ok']:
            return
        
        fail_map = {"跳过": "skip", "重试3次": "retry", "报错": "error"}
        self._add_or_insert_action(insert_index, 'locate_click', image_path=img_var.get(),
            confidence=conf_var.get(), offset_x=offx_var.get(), offset_y=offy_var.get(),
            button=btn_var.get(), on_fail=fail_map.get(fail_var.get(), "skip"))
        self.update_action_list()
    
    def add_locate_click_action_sub(self, callback):
        dialog = tk.Toplevel(self.window)
        dialog.title("图像识别点击")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(400, 300)
        
        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)
        
        ttk.Label(main, text="图像识别点击", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))
        
        img_frame = ttk.LabelFrame(main, text="模板图片", padding=10)
        img_frame.pack(fill='x', pady=5)
        
        img_var = tk.StringVar(value="")
        img_row = ttk.Frame(img_frame)
        img_row.pack(fill='x')
        ttk.Entry(img_row, textvariable=img_var, width=30).pack(side='left')
        
        def browse_img():
            fp = filedialog.askopenfilename(title="选择模板图片",
                filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")],
                parent=dialog)
            if fp:
                img_var.set(fp)
        
        def capture_region():
            import os
            capture_dir = r"C:\Users\ljw\Pictures"
            os.makedirs(capture_dir, exist_ok=True)
            tmp_path = os.path.join(capture_dir, "autoclicker_capture.png")
            if self.screenshot_select_region(tmp_path):
                img_var.set(tmp_path)
                messagebox.showinfo("截图成功", f"已保存到: {tmp_path}", parent=dialog)
        
        ttk.Button(img_row, text="浏览", command=browse_img).pack(side='left', padx=5)
        ttk.Button(img_row, text="截图选区", command=capture_region).pack(side='left')
        
        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)
        
        ttk.Label(param_frame, text="置信度(0.5-1.0):").grid(row=0, column=0, sticky='w')
        conf_var = tk.DoubleVar(value=0.9)
        ttk.Spinbox(param_frame, from_=0.5, to=1.0, increment=0.05, textvariable=conf_var, width=8).grid(row=0, column=1, sticky='w')
        
        ttk.Label(param_frame, text="点击偏移X:").grid(row=1, column=0, sticky='w')
        offx_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offx_var, width=8).grid(row=1, column=1, sticky='w')
        
        ttk.Label(param_frame, text="点击偏移Y:").grid(row=2, column=0, sticky='w')
        offy_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offy_var, width=8).grid(row=2, column=1, sticky='w')
        
        ttk.Label(param_frame, text="鼠标按钮:").grid(row=3, column=0, sticky='w')
        btn_var = tk.StringVar(value="left")
        ttk.Combobox(param_frame, values=["left", "right", "middle"], textvariable=btn_var, width=10, state="readonly").grid(row=3, column=1, sticky='w')
        
        ttk.Label(param_frame, text="失败处理:").grid(row=4, column=0, sticky='w')
        fail_var = tk.StringVar(value="跳过")
        ttk.Combobox(param_frame, values=["跳过", "重试3次", "报错"], textvariable=fail_var, width=10, state="readonly").grid(row=4, column=1, sticky='w')
        
        result = {'ok': False}
        def on_ok():
            if not img_var.get():
                messagebox.showerror("错误", "请选择模板图片", parent=dialog)
                return
            result['ok'] = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right')
        
        self.window.wait_window(dialog)
        
        if not result['ok']:
            return
        
        fail_map = {"跳过": "skip", "重试3次": "retry", "报错": "error"}
        callback({'type': 'locate_click', 'image_path': img_var.get(),
            'confidence': conf_var.get(), 'offset_x': offx_var.get(), 'offset_y': offy_var.get(),
            'button': btn_var.get(), 'on_fail': fail_map.get(fail_var.get(), "skip")})

    def add_ocr_click_action(self, insert_index=None):
        if not OCR_AVAILABLE:
            messagebox.showwarning(
                "未安装 OCR 依赖",
                "未检测到 OCR 引擎，运行该动作时将无法识别文字。\n\n"
                "请运行以下命令安装：\n"
                "pip install rapidocr_onnxruntime\n"
                "（或新版：pip install rapidocr）\n\n"
                "当前仍可继续配置动作，建议安装后使用。",
                parent=self.window)

        dialog = tk.Toplevel(self.window)
        dialog.title("文字定位点击")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(400, 360)

        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text="文字定位点击", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

        text_frame = ttk.LabelFrame(main, text="识别文字", padding=10)
        text_frame.pack(fill='x', pady=5)
        text_var = tk.StringVar(value="")
        ttk.Entry(text_frame, textvariable=text_var, width=30).pack(fill='x')
        ttk.Label(text_frame, text="(先精确匹配，无结果时按包含匹配)", foreground='gray').pack(anchor='w', pady=(3, 0))

        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)

        ttk.Label(param_frame, text="第几个匹配:").grid(row=0, column=0, sticky='w')
        occ_var = tk.IntVar(value=1)
        ttk.Spinbox(param_frame, from_=-1, to=999, increment=1, textvariable=occ_var, width=8).grid(row=0, column=1, sticky='w')
        ttk.Label(param_frame, text="(-1 表示最后一个)").grid(row=0, column=2, sticky='w', padx=(5, 0))

        ttk.Label(param_frame, text="点击偏移X:").grid(row=1, column=0, sticky='w', pady=2)
        offx_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offx_var, width=8).grid(row=1, column=1, sticky='w', pady=2)

        ttk.Label(param_frame, text="点击偏移Y:").grid(row=2, column=0, sticky='w', pady=2)
        offy_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offy_var, width=8).grid(row=2, column=1, sticky='w', pady=2)

        ttk.Label(param_frame, text="识别范围:").grid(row=3, column=0, sticky='w', pady=2)
        region_var = tk.StringVar(value="")
        region_row = ttk.Frame(param_frame)
        region_row.grid(row=3, column=1, columnspan=2, sticky='w', pady=2)
        ttk.Entry(region_row, textvariable=region_var, width=20).pack(side='left')
        def select_region():
            region = self._select_region_coords()
            if region:
                region_var.set(f"{region[0]},{region[1]},{region[2]},{region[3]}")
                messagebox.showinfo("框选成功", f"识别区域: {region_var.get()}", parent=dialog)
        ttk.Button(region_row, text="框选区域", command=select_region).pack(side='left', padx=(5, 0))
        ttk.Label(param_frame, text="(留空=全屏)", foreground='gray').grid(row=3, column=3, sticky='w', padx=(5, 0))

        ttk.Label(param_frame, text="置信度阈值:").grid(row=4, column=0, sticky='w', pady=2)
        score_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(param_frame, from_=0.1, to=1.0, increment=0.05, textvariable=score_var, width=8).grid(row=4, column=1, sticky='w', pady=2)

        ttk.Label(param_frame, text="失败处理:").grid(row=5, column=0, sticky='w', pady=2)
        fail_var = tk.StringVar(value="跳过")
        ttk.Combobox(param_frame, values=["跳过", "重试3次", "报错"], textvariable=fail_var, width=10, state="readonly").grid(row=5, column=1, sticky='w', pady=2)

        result = {'ok': False}
        def on_ok():
            if not text_var.get().strip():
                messagebox.showerror("错误", "请输入要识别的文字", parent=dialog)
                return
            result['ok'] = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right')

        self.window.wait_window(dialog)

        if not result['ok']:
            return

        fail_map = {"跳过": "skip", "重试3次": "retry", "报错": "error"}
        self._add_or_insert_action(insert_index, 'ocr_click', text=text_var.get().strip(),
            occurrence=occ_var.get(), offset_x=offx_var.get(), offset_y=offy_var.get(),
            region=region_var.get().strip(), min_score=score_var.get(),
            on_fail=fail_map.get(fail_var.get(), "skip"))
        self.update_action_list()

    def add_ocr_click_action_sub(self, callback):
        if not OCR_AVAILABLE:
            messagebox.showwarning(
                "未安装 OCR 依赖",
                "未检测到 OCR 引擎，运行该动作时将无法识别文字。\n\n"
                "请运行以下命令安装：\n"
                "pip install rapidocr_onnxruntime\n"
                "（或新版：pip install rapidocr）\n\n"
                "当前仍可继续配置动作，建议安装后使用。",
                parent=self.window)

        dialog = tk.Toplevel(self.window)
        dialog.title("文字定位点击")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(400, 360)

        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text="文字定位点击", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

        text_frame = ttk.LabelFrame(main, text="识别文字", padding=10)
        text_frame.pack(fill='x', pady=5)
        text_var = tk.StringVar(value="")
        ttk.Entry(text_frame, textvariable=text_var, width=30).pack(fill='x')
        ttk.Label(text_frame, text="(先精确匹配，无结果时按包含匹配)", foreground='gray').pack(anchor='w', pady=(3, 0))

        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)

        ttk.Label(param_frame, text="第几个匹配:").grid(row=0, column=0, sticky='w')
        occ_var = tk.IntVar(value=1)
        ttk.Spinbox(param_frame, from_=-1, to=999, increment=1, textvariable=occ_var, width=8).grid(row=0, column=1, sticky='w')
        ttk.Label(param_frame, text="(-1 表示最后一个)").grid(row=0, column=2, sticky='w', padx=(5, 0))

        ttk.Label(param_frame, text="点击偏移X:").grid(row=1, column=0, sticky='w', pady=2)
        offx_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offx_var, width=8).grid(row=1, column=1, sticky='w', pady=2)

        ttk.Label(param_frame, text="点击偏移Y:").grid(row=2, column=0, sticky='w', pady=2)
        offy_var = tk.IntVar(value=0)
        ttk.Entry(param_frame, textvariable=offy_var, width=8).grid(row=2, column=1, sticky='w', pady=2)

        ttk.Label(param_frame, text="识别范围:").grid(row=3, column=0, sticky='w', pady=2)
        region_var = tk.StringVar(value="")
        region_row = ttk.Frame(param_frame)
        region_row.grid(row=3, column=1, columnspan=2, sticky='w', pady=2)
        ttk.Entry(region_row, textvariable=region_var, width=20).pack(side='left')
        def select_region():
            region = self._select_region_coords()
            if region:
                region_var.set(f"{region[0]},{region[1]},{region[2]},{region[3]}")
                messagebox.showinfo("框选成功", f"识别区域: {region_var.get()}", parent=dialog)
        ttk.Button(region_row, text="框选区域", command=select_region).pack(side='left', padx=(5, 0))
        ttk.Label(param_frame, text="(留空=全屏)", foreground='gray').grid(row=3, column=3, sticky='w', padx=(5, 0))

        ttk.Label(param_frame, text="置信度阈值:").grid(row=4, column=0, sticky='w', pady=2)
        score_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(param_frame, from_=0.1, to=1.0, increment=0.05, textvariable=score_var, width=8).grid(row=4, column=1, sticky='w', pady=2)

        ttk.Label(param_frame, text="失败处理:").grid(row=5, column=0, sticky='w', pady=2)
        fail_var = tk.StringVar(value="跳过")
        ttk.Combobox(param_frame, values=["跳过", "重试3次", "报错"], textvariable=fail_var, width=10, state="readonly").grid(row=5, column=1, sticky='w', pady=2)

        result = {'ok': False}
        def on_ok():
            if not text_var.get().strip():
                messagebox.showerror("错误", "请输入要识别的文字", parent=dialog)
                return
            result['ok'] = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right')

        self.window.wait_window(dialog)

        if not result['ok']:
            return

        fail_map = {"跳过": "skip", "重试3次": "retry", "报错": "error"}
        callback({'type': 'ocr_click', 'text': text_var.get().strip(),
            'occurrence': occ_var.get(), 'offset_x': offx_var.get(), 'offset_y': offy_var.get(),
            'region': region_var.get().strip(), 'min_score': score_var.get(),
            'on_fail': fail_map.get(fail_var.get(), "skip")})

    def add_wait_action(self, insert_index=None):
        dialog = tk.Toplevel(self.window)
        dialog.title("添加等待")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(350, 250)
        
        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)
        
        ttk.Label(main, text="等待类型:", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor='w', pady=(0, 5))
        
        wait_type_var = tk.StringVar(value="time")
        wait_combo = ttk.Combobox(main, values=["固定时长", "等待图片出现", "等待窗口出现", 
                                                 "等待剪贴板", "等待按键"], 
                                   width=20, state="readonly")
        wait_combo.pack(anchor='w', pady=(0, 10))
        wait_combo.current(0)
        
        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)
        
        seconds_var = tk.StringVar(value="1.0")
        image_var = tk.StringVar(value="")
        window_var = tk.StringVar(value="")
        text_var = tk.StringVar(value="")
        key_var = tk.StringVar(value="f1")
        timeout_var = tk.StringVar(value="30")
        
        def build_ui(*args):
            for w in param_frame.winfo_children():
                w.destroy()
            idx = wait_combo.current()
            types = ['time', 'image', 'window', 'clipboard', 'key']
            wait_type_var.set(types[idx] if idx >= 0 else 'time')
            
            wt = wait_type_var.get()
            if wt == 'time':
                ttk.Label(param_frame, text="等待秒数:").pack(anchor='w')
                ttk.Entry(param_frame, textvariable=seconds_var, width=10).pack(anchor='w')
            elif wt == 'image':
                ttk.Label(param_frame, text="目标图片:").pack(anchor='w')
                img_row = ttk.Frame(param_frame)
                img_row.pack(fill='x', pady=2)
                ttk.Entry(img_row, textvariable=image_var, width=25).pack(side='left')
                ttk.Button(img_row, text="浏览", 
                          command=lambda: image_var.set(filedialog.askopenfilename(
                              title="选择图片", filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp")],
                              parent=dialog) or image_var.get())).pack(side='left', padx=5)
            elif wt == 'window':
                ttk.Label(param_frame, text="窗口标题关键词:").pack(anchor='w')
                ttk.Entry(param_frame, textvariable=window_var, width=30).pack(anchor='w')
            elif wt == 'clipboard':
                ttk.Label(param_frame, text="剪贴板内容(留空=任意非空):").pack(anchor='w')
                ttk.Entry(param_frame, textvariable=text_var, width=30).pack(anchor='w')
            elif wt == 'key':
                ttk.Label(param_frame, text="等待按键:").pack(anchor='w')
                key_row = ttk.Frame(param_frame)
                key_row.pack(fill='x', pady=2)
                ttk.Entry(key_row, textvariable=key_var, width=15, state='readonly').pack(side='left')
                ttk.Button(key_row, text="选择",
                          command=lambda: key_var.set(self.select_key_dialog("选择按键") or key_var.get())).pack(side='left', padx=5)
            
            ttk.Label(param_frame, text="超时时间(秒):").pack(anchor='w', pady=(10, 0))
            ttk.Entry(param_frame, textvariable=timeout_var, width=10).pack(anchor='w')
        
        wait_combo.bind("<<ComboboxSelected>>", build_ui)
        build_ui()
        
        result = {'ok': False}
        def on_ok():
            result['ok'] = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right')
        
        self.window.wait_window(dialog)
        
        if not result['ok']:
            return
        
        wt = wait_type_var.get()
        try:
            timeout = float(timeout_var.get() or 30)
        except:
            timeout = 30
        
        if wt == 'time':
            try:
                sec = float(seconds_var.get() or 1.0)
            except:
                sec = 1.0
            self._add_or_insert_action(insert_index, 'wait', wait_type='time', seconds=sec, timeout=timeout)
        elif wt == 'image':
            self._add_or_insert_action(insert_index, 'wait', wait_type='image', target_image=image_var.get(), timeout=timeout)
        elif wt == 'window':
            self._add_or_insert_action(insert_index, 'wait', wait_type='window', target_window=window_var.get(), timeout=timeout)
        elif wt == 'clipboard':
            self._add_or_insert_action(insert_index, 'wait', wait_type='clipboard', target_text=text_var.get(), timeout=timeout)
        elif wt == 'key':
            self._add_or_insert_action(insert_index, 'wait', wait_type='key', target_key=key_var.get(), timeout=timeout)
        
        self.update_action_list()
    
    def add_key_action(self, insert_index=None):
        key = self.select_key_dialog("添加按键")
        if key:
            action = self._add_or_insert_action(insert_index, 'press', key=key)
            self.update_action_list()
    
    def add_type_action(self, insert_index=None):
        text = simpledialog.askstring("输入文本", "要输入的文本:", parent=self.window)
        if text is not None:
            action = self._add_or_insert_action(insert_index, 'type', text=text)
            self.update_action_list()
    
    def add_move_action_sub(self, callback):
        try:
            dialog = tk.Toplevel(self.window)
            dialog.title("添加移动")
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.resizable(False, False)

            main = ttk.Frame(dialog, padding=15)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text="鼠标移动", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

            ttk.Label(main, text="坐标类型: 屏幕坐标（相对屏幕左上角）", foreground='#0078D4',
                      font=("Microsoft YaHei UI", 9, "italic")).pack(anchor='w', pady=(0, 8))

            coord_frame = ttk.Frame(main)
            coord_frame.pack(fill='x', pady=5)
            ttk.Label(coord_frame, text="X 坐标:").grid(row=0, column=0, sticky='w', padx=(0, 5))
            x_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=x_var, width=10).grid(row=0, column=1, padx=(0, 15))
            ttk.Label(coord_frame, text="Y 坐标:").grid(row=0, column=2, sticky='w', padx=(0, 5))
            y_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=y_var, width=10).grid(row=0, column=3)

            btn_row = ttk.Frame(main)
            btn_row.pack(fill='x', pady=5)
            def get_pos():
                pos = self.autoclicker.get_current_position()
                x_var.set(pos.x)
                y_var.set(pos.y)
            ttk.Button(btn_row, text="获取当前鼠标位置 (F2)", command=get_pos).pack(side='left', padx=(0, 10))

            if self.position_cache:
                cache_items = [f"[{p['time']}] X={p['x']}, Y={p['y']}" for p in self.position_cache]
                def on_cache_select(*args):
                    sel = cache_combo.current()
                    if sel >= 0:
                        p = self.position_cache[sel]
                        x_var.set(p['x'])
                        y_var.set(p['y'])
                ttk.Label(btn_row, text="F2记录:").pack(side='left')
                cache_combo = ttk.Combobox(btn_row, values=cache_items, width=22, state="readonly")
                cache_combo.pack(side='left', padx=(5, 0))
                cache_combo.bind("<<ComboboxSelected>>", on_cache_select)

            dur_frame = ttk.Frame(main)
            dur_frame.pack(fill='x', pady=5)
            ttk.Label(dur_frame, text="移动时间(秒, 0=瞬移):").pack(side='left')
            dur_var = tk.StringVar(value="0")
            ttk.Entry(dur_frame, textvariable=dur_var, width=8).pack(side='left', padx=(5, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            ttk.Button(main, text="确定", command=on_ok).pack(side='right', padx=5, pady=(10, 0))
            ttk.Button(main, text="取消", command=lambda: dialog.destroy()).pack(side='right', pady=(10, 0))

            self.window.wait_window(dialog)
            if not result['ok']:
                return
            callback({'type': 'move', 'x': x_var.get(), 'y': y_var.get(), 'duration': float(dur_var.get())})
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字", parent=self.window)
    
    def add_move_rel_action_sub(self, callback):
        try:
            dialog = tk.Toplevel(self.window)
            dialog.title("相对移动")
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.resizable(False, False)

            main = ttk.Frame(dialog, padding=15)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text="相对移动", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

            coord_frame = ttk.Frame(main)
            coord_frame.pack(fill='x', pady=5)
            ttk.Label(coord_frame, text="水平位移(dx):").grid(row=0, column=0, sticky='w', padx=(0, 5))
            dx_var = tk.IntVar(value=100)
            ttk.Entry(coord_frame, textvariable=dx_var, width=10).grid(row=0, column=1, padx=(0, 15))
            ttk.Label(coord_frame, text="垂直位移(dy):").grid(row=0, column=2, sticky='w', padx=(0, 5))
            dy_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=dy_var, width=10).grid(row=0, column=3)

            dur_frame = ttk.Frame(main)
            dur_frame.pack(fill='x', pady=5)
            ttk.Label(dur_frame, text="移动时间(秒, 0=瞬移):").pack(side='left')
            dur_var = tk.StringVar(value="0")
            ttk.Entry(dur_frame, textvariable=dur_var, width=8).pack(side='left', padx=(5, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            ttk.Button(main, text="确定", command=on_ok).pack(side='right', padx=5, pady=(10, 0))
            ttk.Button(main, text="取消", command=lambda: dialog.destroy()).pack(side='right', pady=(10, 0))

            self.window.wait_window(dialog)
            if not result['ok']:
                return
            callback({'type': 'move_rel', 'dx': dx_var.get(), 'dy': dy_var.get(), 'duration': float(dur_var.get())})
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字", parent=self.window)
    
    def add_click_action_sub(self, callback):
        callback({'type': 'click', 'button': 'left', 'clicks': 1})
    
    def add_right_click_action_sub(self, callback):
        callback({'type': 'click', 'button': 'right', 'clicks': 1})
    
    def add_double_click_action_sub(self, callback):
        callback({'type': 'click', 'button': 'left', 'clicks': 2})
    
    def add_wait_action_sub(self, callback):
        dialog = tk.Toplevel(self.window)
        dialog.title("添加等待")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.minsize(350, 250)
        
        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)
        
        ttk.Label(main, text="等待类型:", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor='w', pady=(0, 5))
        
        wait_type_var = tk.StringVar(value="time")
        wait_combo = ttk.Combobox(main, values=["固定时长", "等待图片出现", "等待窗口出现", 
                                                 "等待剪贴板", "等待按键"], 
                                   width=20, state="readonly")
        wait_combo.pack(anchor='w', pady=(0, 10))
        wait_combo.current(0)
        
        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)
        
        seconds_var = tk.StringVar(value="1.0")
        image_var = tk.StringVar(value="")
        window_var = tk.StringVar(value="")
        text_var = tk.StringVar(value="")
        key_var = tk.StringVar(value="f1")
        timeout_var = tk.StringVar(value="30")
        
        def build_ui(*args):
            for w in param_frame.winfo_children():
                w.destroy()
            idx = wait_combo.current()
            types = ['time', 'image', 'window', 'clipboard', 'key']
            wait_type_var.set(types[idx] if idx >= 0 else 'time')
            
            wt = wait_type_var.get()
            if wt == 'time':
                ttk.Label(param_frame, text="等待秒数:").pack(anchor='w')
                ttk.Entry(param_frame, textvariable=seconds_var, width=10).pack(anchor='w')
            elif wt == 'image':
                ttk.Label(param_frame, text="目标图片:").pack(anchor='w')
                img_row = ttk.Frame(param_frame)
                img_row.pack(fill='x', pady=2)
                ttk.Entry(img_row, textvariable=image_var, width=25).pack(side='left')
                ttk.Button(img_row, text="浏览", 
                          command=lambda: image_var.set(filedialog.askopenfilename(
                              title="选择图片", filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp")],
                              parent=dialog) or image_var.get())).pack(side='left', padx=5)
            elif wt == 'window':
                ttk.Label(param_frame, text="窗口标题关键词:").pack(anchor='w')
                ttk.Entry(param_frame, textvariable=window_var, width=30).pack(anchor='w')
            elif wt == 'clipboard':
                ttk.Label(param_frame, text="剪贴板内容(留空=任意非空):").pack(anchor='w')
                ttk.Entry(param_frame, textvariable=text_var, width=30).pack(anchor='w')
            elif wt == 'key':
                ttk.Label(param_frame, text="等待按键:").pack(anchor='w')
                key_row = ttk.Frame(param_frame)
                key_row.pack(fill='x', pady=2)
                ttk.Entry(key_row, textvariable=key_var, width=15, state='readonly').pack(side='left')
                ttk.Button(key_row, text="选择",
                          command=lambda: key_var.set(self.select_key_dialog("选择按键") or key_var.get())).pack(side='left', padx=5)
            
            ttk.Label(param_frame, text="超时时间(秒):").pack(anchor='w', pady=(10, 0))
            ttk.Entry(param_frame, textvariable=timeout_var, width=10).pack(anchor='w')
        
        wait_combo.bind("<<ComboboxSelected>>", build_ui)
        build_ui()
        
        result = {'ok': False}
        def on_ok():
            result['ok'] = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right')
        
        self.window.wait_window(dialog)
        
        if not result['ok']:
            return
        
        wt = wait_type_var.get()
        try:
            timeout = float(timeout_var.get() or 30)
        except:
            timeout = 30
        
        params = {'type': 'wait', 'timeout': timeout, 'wait_type': wt}
        if wt == 'time':
            try:
                params['seconds'] = float(seconds_var.get() or 1.0)
            except:
                params['seconds'] = 1.0
        elif wt == 'image':
            params['target_image'] = image_var.get()
        elif wt == 'window':
            params['target_window'] = window_var.get()
        elif wt == 'clipboard':
            params['target_text'] = text_var.get()
        elif wt == 'key':
            params['target_key'] = key_var.get()
        
        callback(params)
    
    def add_key_action_sub(self, callback):
        key = self.select_key_dialog("添加按键")
        if key:
            callback({'type': 'press', 'key': key})
    
    def add_type_action_sub(self, callback):
        text = simpledialog.askstring("输入文本", "要输入的文本:", parent=self.window)
        if text is not None:
            callback({'type': 'type', 'text': text})

    def add_open_file_action(self, insert_index=None):
        filepath = filedialog.askopenfilename(
            title="选择要打开的文件",
            filetypes=[("所有文件", "*.*")]
        )
        if filepath:
            self._add_or_insert_action(insert_index, 'open_file', filepath=filepath)
            self.update_action_list()

    def add_open_file_action_sub(self, callback):
        filepath = filedialog.askopenfilename(
            title="选择要打开的文件",
            filetypes=[("所有文件", "*.*")]
        )
        if filepath:
            callback({'type': 'open_file', 'filepath': filepath})

    def add_open_url_action(self, insert_index=None):
        url = simpledialog.askstring("打开网站", "请输入网址URL:", parent=self.window)
        if url:
            self._add_or_insert_action(insert_index, 'open_url', url=url)
            self.update_action_list()

    def _select_region_coords(self):
        import time
        self.window.withdraw()
        time.sleep(0.5)

        screen_w, screen_h = pyautogui.size()

        selector = tk.Toplevel()
        selector.attributes('-fullscreen', True)
        selector.attributes('-topmost', True)
        selector.overrideredirect(True)
        selector.configure(bg='black')

        from PIL import ImageTk
        full_img = pyautogui.screenshot()
        img_tk = ImageTk.PhotoImage(full_img)

        canvas = tk.Canvas(selector, highlightthickness=0, cursor='crosshair',
                          bg='black', width=screen_w, height=screen_h)
        canvas.pack(fill='both', expand=True)

        bg_id = canvas.create_image(0, 0, anchor='nw', image=img_tk)
        canvas.image = img_tk

        overlay = canvas.create_rectangle(0, 0, screen_w, screen_h,
                                          fill='black', stipple='gray50')

        hint = canvas.create_text(screen_w // 2, 40,
                                 text='拖拽鼠标框选 OCR 识别区域，松开完成，按 ESC 取消',
                                 fill='yellow', font=('Microsoft YaHei UI', 16, 'bold'))

        start_x = start_y = 0
        sel_rect = None
        result = {'region': None, 'cancelled': False}

        def on_press(event):
            nonlocal start_x, start_y, sel_rect
            pos = pyautogui.position()
            start_x, start_y = pos.x, pos.y
            sel_rect = canvas.create_rectangle(start_x, start_y, start_x, start_y,
                                               outline='red', width=3, fill='', stipple='')

        def on_drag(event):
            if sel_rect:
                pos = pyautogui.position()
                canvas.coords(sel_rect, start_x, start_y, pos.x, pos.y)

        def on_release(event):
            nonlocal result
            pos = pyautogui.position()
            end_x, end_y = pos.x, pos.y

            x1 = min(start_x, end_x)
            y1 = min(start_y, end_y)
            x2 = max(start_x, end_x)
            y2 = max(start_y, end_y)

            w = x2 - x1
            h = y2 - y1

            if w > 5 and h > 5:
                result['region'] = (x1, y1, w, h)
            selector.destroy()

        def on_esc(event=None):
            result['cancelled'] = True
            selector.destroy()

        selector.bind_all('<Button-1>', on_press)
        selector.bind_all('<B1-Motion>', on_drag)
        selector.bind_all('<ButtonRelease-1>', on_release)
        selector.bind_all('<Key-Escape>', on_esc)
        selector.bind_all('<KeyPress-Escape>', on_esc)
        selector.protocol("WM_DELETE_WINDOW", on_esc)

        selector.focus_force()
        selector.grab_set()

        self.window.wait_window(selector)

        self.window.deiconify()
        self.window.lift()

        if result['cancelled'] or not result['region']:
            return None
        return result['region']

    def open_ocr_dialog(self):
        if not OCR_AVAILABLE:
            messagebox.showinfo(
                "未安装 OCR 依赖",
                "未检测到 OCR 引擎。\n\n"
                "请运行以下命令安装后重试：\n"
                "pip install rapidocr_onnxruntime\n"
                "（或新版：pip install rapidocr）\n\n"
                "安装后重新启动本程序即可使用屏幕文字识别功能。",
                parent=self.window)
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("屏幕文字识别")
        dialog.transient(self.window)
        dialog.resizable(True, True)
        dialog.minsize(680, 480)

        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text="屏幕文字识别", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

        range_frame = ttk.LabelFrame(main, text="识别范围", padding=10)
        range_frame.pack(fill='x', pady=5)

        range_var = tk.StringVar(value="全屏")
        ttk.Radiobutton(range_frame, text="全屏", variable=range_var, value="全屏").pack(side='left', padx=5)
        ttk.Radiobutton(range_frame, text="选区", variable=range_var, value="选区").pack(side='left', padx=5)

        region_var = tk.StringVar(value="")
        ttk.Entry(range_frame, textvariable=region_var, width=26).pack(side='left', padx=(10, 5))

        def select_region():
            region = self._select_region_coords()
            if region:
                region_var.set(f"{region[0]},{region[1]},{region[2]},{region[3]}")

        ttk.Button(range_frame, text="框选区域", command=select_region).pack(side='left')
        ttk.Label(range_frame, text="(框选后自动填入 x,y,w,h)", foreground='gray').pack(side='left', padx=5)

        param_frame = ttk.LabelFrame(main, text="参数", padding=10)
        param_frame.pack(fill='x', pady=5)

        ttk.Label(param_frame, text="最低置信度:").pack(side='left')
        min_score_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(param_frame, from_=0.0, to=1.0, increment=0.05,
                    textvariable=min_score_var, width=6).pack(side='left', padx=(5, 20))

        ttk.Label(param_frame, text="保存结果:").pack(side='left')
        save_var = tk.StringVar(value="")
        ttk.Entry(param_frame, textvariable=save_var, width=26).pack(side='left', padx=(5, 5))

        def browse_save():
            fp = filedialog.asksaveasfilename(title="保存识别结果", defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("JSON 文件", "*.json")], parent=dialog)
            if fp:
                save_var.set(fp)

        ttk.Button(param_frame, text="浏览", command=browse_save).pack(side='left', padx=(0, 20))

        ttk.Label(param_frame, text="缩放比例:").pack(side='left')
        scale_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(param_frame, from_=0.1, to=1.0, increment=0.1,
                    textvariable=scale_var, width=6).pack(side='left', padx=(5, 5))
        ttk.Label(param_frame, text="(0.5 可提速)", foreground='gray').pack(side='left')

        ctrl_frame = ttk.Frame(main)
        ctrl_frame.pack(fill='x', pady=8)
        identify_btn = ttk.Button(ctrl_frame, text="开始识别", width=14)
        identify_btn.pack(side='left')
        status_label = ttk.Label(ctrl_frame, text="", foreground=self.COLOR_PRIMARY)
        status_label.pack(side='left', padx=10)

        result_frame = ttk.LabelFrame(main, text="识别结果", padding=10)
        result_frame.pack(fill='both', expand=True, pady=5)

        filter_frame = ttk.Frame(result_frame)
        filter_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(filter_frame, text="搜索过滤:").pack(side='left')
        filter_var = tk.StringVar(value="")
        filter_entry = ttk.Entry(filter_frame, textvariable=filter_var, width=32)
        filter_entry.pack(side='left', padx=(5, 8))
        ttk.Label(filter_frame, text="(输入关键词后表格实时过滤)", foreground='gray').pack(side='left')

        columns = ('text', 'cx', 'cy', 'w', 'h', 'score')
        tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=10)
        tree.heading('text', text='文字')
        tree.heading('cx', text='中心X')
        tree.heading('cy', text='中心Y')
        tree.heading('w', text='宽度')
        tree.heading('h', text='高度')
        tree.heading('score', text='置信度')
        tree.column('text', width=260, anchor='w')
        tree.column('cx', width=70, anchor='center')
        tree.column('cy', width=70, anchor='center')
        tree.column('w', width=60, anchor='center')
        tree.column('h', width=60, anchor='center')
        tree.column('score', width=80, anchor='center')

        vsb = ttk.Scrollbar(result_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        tree.tag_configure('odd', background=self.COLOR_CARD_ALT)

        ocr_results = []

        bottom_frame = ttk.Frame(main)
        bottom_frame.pack(fill='x', pady=(8, 0))
        insert_click_btn = ttk.Button(bottom_frame, text="插入点击动作",
                   command=lambda: _insert_click_action())
        insert_click_btn.pack(side='left', padx=5)
        insert_ocr_click_btn = ttk.Button(bottom_frame, text="插入文字定位动作",
                   command=lambda: _insert_ocr_click_action())
        insert_ocr_click_btn.pack(side='left', padx=5)
        copy_btn = ttk.Button(bottom_frame, text="复制全部坐标",
                   command=lambda: _copy_all_coords())
        copy_btn.pack(side='left', padx=5)
        export_btn = ttk.Button(bottom_frame, text="导出结果到文件",
                   command=lambda: _export_results())
        export_btn.pack(side='left', padx=5)
        ttk.Button(bottom_frame, text="关闭",
                   command=dialog.destroy).pack(side='right', padx=5)

        def _set_controls_enabled(enabled):
            state = 'normal' if enabled else 'disabled'
            identify_btn.config(state=state)
            insert_click_btn.config(state=state)
            insert_ocr_click_btn.config(state=state)
            copy_btn.config(state=state)
            export_btn.config(state=state)

        def _refresh_tree(rows):
            for item in tree.get_children():
                tree.delete(item)
            if not rows:
                return
            for i, r in enumerate(rows):
                tag = 'odd' if i % 2 else ''
                tree.insert('', 'end', values=(
                    r['text'], r['cx'], r['cy'], r['w'], r['h'],
                    f"{r['score']:.3f}"), tags=(tag,))

        def _apply_filter(*args):
            keyword = filter_var.get().strip().lower()
            if not keyword:
                _refresh_tree(ocr_results)
                return
            _refresh_tree([r for r in ocr_results if keyword in r['text'].lower()])

        filter_var.trace_add('write', _apply_filter)

        def _run_ocr():
            try:
                _set_controls_enabled(False)
                identify_btn.config(text="识别中...")
                status_label.config(text="正在识别中，请稍候...")
                for item in tree.get_children():
                    tree.delete(item)
                ocr_results.clear()
                region_str = ""
                if range_var.get() == "选区":
                    region_str = region_var.get().strip()
                save_path = save_var.get().strip() or None
                results = self.autoclicker.ocr_read(
                    region=region_str or None,
                    save_path=save_path,
                    min_score=float(min_score_var.get()),
                    scale=float(scale_var.get()))
                dialog.after(0, lambda: _fill_results(results))
            except Exception as e:
                dialog.after(0, lambda: messagebox.showerror("OCR 识别失败", str(e), parent=dialog))
            finally:
                dialog.after(0, lambda: _set_controls_enabled(True))
                dialog.after(0, lambda: identify_btn.config(text="开始识别"))

        def _fill_results(results):
            for item in tree.get_children():
                tree.delete(item)
            if not results:
                status_label.config(text="未识别到文字（可调低置信度阈值或检查识别区域）")
                return
            ocr_results[:] = results
            _apply_filter()
            status_label.config(text=f"共识别到 {len(results)} 个文字块（双击行可插入点击动作）")

        identify_btn.config(command=lambda: threading.Thread(target=_run_ocr, daemon=True).start())

        def _insert_click_action():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("提示", "请先在表格中选择一行文字", parent=dialog)
                return
            values = tree.item(sel[0], 'values')
            try:
                cx = int(values[1])
                cy = int(values[2])
            except (TypeError, ValueError):
                messagebox.showerror("错误", "无法解析选中行的坐标", parent=dialog)
                return
            self._add_or_insert_action(None, 'move', x=cx, y=cy, duration=0)
            self._add_or_insert_action(None, 'click', button='left', clicks=1)
            self.update_action_list()
            messagebox.showinfo("已插入", f"已插入点击动作：移动+左键点击（{cx}, {cy}）", parent=dialog)

        def _insert_ocr_click_action():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("提示", "请先在表格中选择一行文字", parent=dialog)
                return
            values = tree.item(sel[0], 'values')
            text_val = str(values[0])
            try:
                cx = int(values[1])
                cy = int(values[2])
            except (TypeError, ValueError):
                messagebox.showerror("错误", "无法解析选中行的坐标", parent=dialog)
                return
            target_block = None
            for r in ocr_results:
                if r['text'] == text_val and r['cx'] == cx and r['cy'] == cy:
                    target_block = r
                    break
            if target_block is None:
                for r in ocr_results:
                    if r['text'] == text_val:
                        target_block = r
                        break
            occurrence = 1
            if target_block is not None:
                matched = [r for r in ocr_results if r['text'] == text_val]
                if not matched:
                    matched = [r for r in ocr_results if text_val in r['text']]
                for i, r in enumerate(matched, 1):
                    if r is target_block:
                        occurrence = i
                        break
            self._add_or_insert_action(None, 'ocr_click', text=text_val, occurrence=occurrence)
            self.update_action_list()
            messagebox.showinfo("已插入",
                f"已插入文字定位动作：ocr_click('{text_val}', occurrence={occurrence})", parent=dialog)

        tree.bind('<Double-1>', lambda e: _insert_click_action())

        def _copy_all_coords():
            if not ocr_results:
                messagebox.showinfo("提示", "当前没有识别结果", parent=dialog)
                return
            lines = [f"{r['text']}\t{r['cx']},{r['cy']}" for r in ocr_results]
            dialog.clipboard_clear()
            dialog.clipboard_append('\n'.join(lines))
            messagebox.showinfo("已复制", f"已复制 {len(lines)} 条坐标到剪贴板", parent=dialog)

        def _export_results():
            if not ocr_results:
                messagebox.showinfo("提示", "当前没有识别结果", parent=dialog)
                return
            fp = filedialog.asksaveasfilename(title="导出识别结果", defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("JSON 文件", "*.json")], parent=dialog)
            if not fp:
                return
            try:
                if str(fp).lower().endswith('.json'):
                    with open(fp, 'w', encoding='utf-8') as f:
                        json.dump(ocr_results, f, ensure_ascii=False, indent=2)
                else:
                    with open(fp, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(
                            f"{r['text']}\t{r['x']},{r['y']},{r['w']},{r['h']}\t"
                            f"中心({r['cx']},{r['cy']})\t置信度 {r['score']:.3f}"
                            for r in ocr_results))
                messagebox.showinfo("导出成功", f"已导出到: {fp}", parent=dialog)
            except Exception as e:
                messagebox.showerror("导出失败", str(e), parent=dialog)

    def add_open_url_action_sub(self, callback):
        url = simpledialog.askstring("打开网站", "请输入网址URL:", parent=self.window)
        if url:
            callback({'type': 'open_url', 'url': url})
    
    def add_drag_action_sub(self, callback):
        try:
            dialog = tk.Toplevel(self.window)
            dialog.title("添加拖拽")
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.resizable(False, False)

            main = ttk.Frame(dialog, padding=15)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text="鼠标拖拽", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

            ttk.Label(main, text="坐标类型: 屏幕坐标（相对屏幕左上角）", foreground='#0078D4',
                      font=("Microsoft YaHei UI", 9, "italic")).pack(anchor='w', pady=(0, 8))

            coord_frame = ttk.Frame(main)
            coord_frame.pack(fill='x', pady=5)
            ttk.Label(coord_frame, text="X 目标:").grid(row=0, column=0, sticky='w', padx=(0, 5))
            x_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=x_var, width=10).grid(row=0, column=1, padx=(0, 15))
            ttk.Label(coord_frame, text="Y 目标:").grid(row=0, column=2, sticky='w', padx=(0, 5))
            y_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=y_var, width=10).grid(row=0, column=3)

            btn_row = ttk.Frame(main)
            btn_row.pack(fill='x', pady=5)
            def get_pos():
                pos = self.autoclicker.get_current_position()
                x_var.set(pos.x)
                y_var.set(pos.y)
            ttk.Button(btn_row, text="获取当前鼠标位置 (F2)", command=get_pos).pack(side='left', padx=(0, 10))

            if self.position_cache:
                cache_items = [f"[{p['time']}] X={p['x']}, Y={p['y']}" for p in self.position_cache]
                def on_cache_select(*args):
                    sel = cache_combo.current()
                    if sel >= 0:
                        p = self.position_cache[sel]
                        x_var.set(p['x'])
                        y_var.set(p['y'])
                ttk.Label(btn_row, text="F2记录:").pack(side='left')
                cache_combo = ttk.Combobox(btn_row, values=cache_items, width=22, state="readonly")
                cache_combo.pack(side='left', padx=(5, 0))
                cache_combo.bind("<<ComboboxSelected>>", on_cache_select)

            dur_frame = ttk.Frame(main)
            dur_frame.pack(fill='x', pady=5)
            ttk.Label(dur_frame, text="拖拽时间(秒, 0=瞬移):").pack(side='left')
            dur_var = tk.StringVar(value="0")
            ttk.Entry(dur_frame, textvariable=dur_var, width=8).pack(side='left', padx=(5, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            ttk.Button(main, text="确定", command=on_ok).pack(side='right', padx=5, pady=(10, 0))
            ttk.Button(main, text="取消", command=lambda: dialog.destroy()).pack(side='right', pady=(10, 0))

            self.window.wait_window(dialog)
            if not result['ok']:
                return
            callback({'type': 'drag', 'x': x_var.get(), 'y': y_var.get(), 'duration': float(dur_var.get())})
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字", parent=self.window)
    
    def add_scroll_action_sub(self, callback):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("鼠标滚轮控制 - 子动作模式", 0.5, 0.4)
            
            ttk.Label(dialog, text="滚轮滚动设置", font=self.FONT_HEADING).pack(pady=self.PAD_MD)
            
            direction_frame = ttk.Frame(dialog)
            direction_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(direction_frame, text="滚动方向:").pack(side='left', padx=self.PAD_XS)
            direction_var = tk.StringVar(value="up")
            direction_frame2 = ttk.Frame(direction_frame)
            direction_frame2.pack(side='left', padx=self.PAD_XS)
            ttk.Radiobutton(direction_frame2, text="向上", variable=direction_var, value="up").pack(side='left', padx=self.PAD_XS)
            ttk.Radiobutton(direction_frame2, text="向下", variable=direction_var, value="down").pack(side='left', padx=self.PAD_XS)
            ttk.Label(direction_frame, text="   ").pack(side='left')
            ttk.Radiobutton(direction_frame, text="向左", variable=direction_var, value="left").pack(side='left', padx=self.PAD_XS)
            ttk.Radiobutton(direction_frame, text="向右", variable=direction_var, value="right").pack(side='left', padx=self.PAD_XS)
            
            amount_frame = ttk.Frame(dialog)
            amount_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(amount_frame, text="滚动量:").pack(side='left', padx=self.PAD_XS)
            amount_var = tk.IntVar(value=10)
            amount_label = ttk.Label(amount_frame, text="10", width=4)
            amount_label.pack(side='left', padx=self.PAD_XS)
            
            def update_amount_label(val):
                amount_label.config(text=str(int(float(val))))
            
            amount_scale = tk.Scale(amount_frame, from_=1, to=100, orient='horizontal', 
                                   variable=amount_var, length=200, showvalue=0,
                                   command=update_amount_label)
            amount_scale.pack(side='left', padx=self.PAD_MD)
            
            speed_frame = ttk.Frame(dialog)
            speed_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(speed_frame, text="滚动间隔:").pack(side='left', padx=self.PAD_XS)
            speed_var = tk.DoubleVar(value=0.1)
            speed_label = ttk.Label(speed_frame, text="0.1", width=6)
            speed_label.pack(side='left', padx=self.PAD_XS)
            
            def update_speed_label(val):
                speed_label.config(text=f"{float(val):.1f}")
            
            speed_scale = tk.Scale(speed_frame, from_=0, to=2, orient='horizontal', 
                                  variable=speed_var, resolution=0.1, length=200, showvalue=0,
                                  command=update_speed_label)
            speed_scale.pack(side='left', padx=self.PAD_MD)
            ttk.Label(speed_frame, text="秒（0为连续滚动）").pack(side='left', padx=self.PAD_XS)
            
            repeat_frame = ttk.Frame(dialog)
            repeat_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(repeat_frame, text="重复次数:").pack(side='left', padx=self.PAD_XS)
            repeat_var = tk.IntVar(value=1)
            repeat_label = ttk.Label(repeat_frame, text="1", width=4)
            repeat_label.pack(side='left', padx=self.PAD_XS)
            
            def update_repeat_label(val):
                repeat_label.config(text=str(int(float(val))))
            
            repeat_scale = tk.Scale(repeat_frame, from_=1, to=50, orient='horizontal',
                                   variable=repeat_var, length=200, showvalue=0,
                                   command=update_repeat_label)
            repeat_scale.pack(side='left', padx=self.PAD_MD)
            ttk.Label(repeat_frame, text="次").pack(side='left', padx=self.PAD_XS)
            
            result = {'confirmed': False, 'params': {}}
            
            def on_confirm():
                try:
                    direction = direction_var.get()
                    amount = amount_var.get()
                    interval = speed_var.get()
                    repeat = repeat_var.get()
                    
                    if direction == "up":
                        clicks = amount
                        scroll_direction = 'vertical'
                    elif direction == "down":
                        clicks = -amount
                        scroll_direction = 'vertical'
                    elif direction == "left":
                        clicks = -amount
                        scroll_direction = 'horizontal'
                    else:
                        clicks = amount
                        scroll_direction = 'horizontal'
                    
                    result['confirmed'] = True
                    result['params'] = {
                        'clicks': clicks,
                        'direction': scroll_direction,
                        'amount': amount,
                        'interval': interval,
                        'repeat': repeat
                    }
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showerror("错误", f"请输入有效的数字: {e}", parent=dialog)
            
            def on_cancel():
                dialog.destroy()
            
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=self.PAD_MD)
            
            ttk.Button(btn_frame, text="确定", command=on_confirm).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='left', padx=self.PAD_MD)
            
            self.window.wait_window(dialog)
            
            if result['confirmed']:
                params = result['params']
                for i in range(params['repeat']):
                    callback({'type': 'scroll',
                             'clicks': params['clicks'],
                             'direction': params['direction']})
                    if params['interval'] > 0 and i < params['repeat'] - 1:
                        callback({'type': 'wait', 'wait_type': 'time', 'seconds': params['interval'], 'timeout': 30})
        except Exception as e:
            messagebox.showerror("错误", f"添加滚动动作时出错: {e}", parent=self.window)
    
    def add_hold_action_sub(self, callback):
        try:
            button_type = simpledialog.askstring("按钮类型", "按钮类型(left/right):", 
                                               parent=self.window, initialvalue="left")
            if button_type not in ['left', 'right']:
                messagebox.showerror("错误", "按钮类型只能是 left 或 right", parent=self.window)
                return
                
            duration = simpledialog.askfloat("长按时间", "长按时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if duration:
                callback({'type': 'hold', 'button': button_type, 'duration': duration})
        except Exception as e:
            messagebox.showerror("错误", f"添加长按动作时出错: {e}", parent=self.window)
    
    def add_key_hold_action_sub(self, callback):
        try:
            key = self.select_key_dialog("添加键盘长按")
            if not key:
                return
                
            duration = simpledialog.askfloat("长按时间", "长按时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if duration:
                callback({'type': 'key_hold', 'key': key, 'duration': duration})
        except Exception as e:
            messagebox.showerror("错误", f"添加键盘长按动作时出错: {e}", parent=self.window)
    
    def add_multi_key_action_sub(self, callback):
        try:
            self.window.lift()
            self.window.focus_force()
            
            keys = self.select_multi_keys_dialog("多按键同步")
            if not keys:
                return
            
            self.window.lift()
            
            duration = simpledialog.askfloat("持续时间", "持续时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if not duration:
                return
                
            callback({'type': 'multi_key', 'keys': keys, 'duration': duration})
        except Exception as e:
            messagebox.showerror("错误", f"添加多按键同步动作时出错: {e}", parent=self.window)
    
    def add_multi_mouse_action_sub(self, callback):
        try:
            self.window.lift()
            self.window.focus_force()
            
            buttons_input = simpledialog.askstring("多鼠标按键同步", "鼠标按键(left,right,middle):", 
                                               parent=self.window, initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            self.window.lift()
            
            duration = simpledialog.askfloat("持续时间", "持续时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if not duration:
                return
                
            callback({'type': 'multi_mouse', 'buttons': buttons, 'duration': duration})
        except Exception as e:
            messagebox.showerror("错误", f"添加多鼠标按键同步动作时出错: {e}", parent=self.window)
    
    def add_multi_key_mouse_action_sub(self, callback):
        try:
            self.window.lift()
            self.window.focus_force()
            
            keys = self.select_multi_keys_dialog("选择键盘按键")
            if not keys:
                return
            
            self.window.lift()
            
            buttons_input = simpledialog.askstring("鼠标按键", "鼠标按键(left,right,middle):", 
                                                 parent=self.window, initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            self.window.lift()
            
            duration = simpledialog.askfloat("持续时间", "持续时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if not duration:
                return
                
            callback({'type': 'multi_key_mouse', 'keys': keys, 'buttons': buttons, 'duration': duration})
        except Exception as e:
            messagebox.showerror("错误", f"添加键盘与鼠标同步动作时出错: {e}", parent=self.window)
    
    
    def add_fill_action_sub(self, callback):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("填充数字设置 - 子动作模式", 0.5, 0.5)

            canvas = tk.Canvas(dialog, borderwidth=0, background=self.COLOR_CARD)
            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")

            dialog.grid_rowconfigure(0, weight=1)
            dialog.grid_columnconfigure(0, weight=1)

            ttk.Label(scrollable_frame, text="总位数:").grid(row=0, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            total_var = tk.StringVar(value="4")
            total_spin = ttk.Spinbox(scrollable_frame, from_=1, to=10, textvariable=total_var, width=10)
            total_spin.grid(row=0, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="起始数字:").grid(row=1, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            start_var = tk.StringVar(value="0")
            start_entry = ttk.Entry(scrollable_frame, textvariable=start_var, width=12)
            start_entry.grid(row=1, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="结束数字:").grid(row=2, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            end_var = tk.StringVar(value="9999")
            end_entry = ttk.Entry(scrollable_frame, textvariable=end_var, width=12)
            end_entry.grid(row=2, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="前缀(固定):").grid(row=3, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            prefix_var = tk.StringVar(value="")
            prefix_entry = ttk.Entry(scrollable_frame, textvariable=prefix_var, width=12)
            prefix_entry.grid(row=3, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="后缀(固定):").grid(row=4, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            suffix_var = tk.StringVar(value="")
            suffix_entry = ttk.Entry(scrollable_frame, textvariable=suffix_var, width=12)
            suffix_entry.grid(row=4, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="输入间隔(秒):").grid(row=5, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            interval_var = tk.StringVar(value="0.5")
            interval_spin = ttk.Spinbox(scrollable_frame, from_=0, to=10, increment=0.1, textvariable=interval_var, width=10)
            interval_spin.grid(row=5, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            example_frame = ttk.LabelFrame(scrollable_frame, text="示例预览", padding=self.PAD_MD)
            example_frame.grid(row=6, column=0, columnspan=2, sticky='ew', padx=self.PAD_MD, pady=self.PAD_XS)

            example_label = ttk.Label(example_frame, text="", foreground=self.COLOR_PRIMARY, font=self.FONT_HEADING)
            example_label.pack(anchor='w')

            def update_example(*args):
                try:
                    total = int(total_var.get())
                    start = int(start_var.get())
                    end = int(end_var.get())
                    prefix = prefix_var.get()
                    suffix = suffix_var.get()

                    fixed_len = len(prefix) + len(suffix)
                    if fixed_len >= total:
                        example_label.config(text="错误: 前缀+后缀长度不能大于总位数")
                        return

                    fill_digits = total - fixed_len
                    if fill_digits <= 0:
                        example_label.config(text="错误: 填充位数必须大于0")
                        return

                    max_val = 10 ** fill_digits - 1
                    if start > max_val:
                        start = 0
                        start_var.set("0")
                    if end > max_val:
                        end = max_val
                        end_var.set(str(max_val))
                    if start > end:
                        start, end = end, start
                        start_var.set(str(start))
                        end_var.set(str(end))

                    first_num = str(start).zfill(fill_digits)
                    last_num = str(end).zfill(fill_digits)
                    first_full = prefix + first_num + suffix
                    last_full = prefix + last_num + suffix

                    count = end - start + 1
                    example_label.config(text=f"格式: {first_full} ~ {last_full}\n每次填1个数字，总计 {count} 个")
                except ValueError:
                    example_label.config(text="请输入有效的数字")

            total_var.trace('w', update_example)
            start_var.trace('w', update_example)
            end_var.trace('w', update_example)
            prefix_var.trace('w', update_example)
            suffix_var.trace('w', update_example)

            update_example()

            help_text = ttk.Label(scrollable_frame, text="说明: 每次运行脚本只填入一个数字\n前缀/后缀为固定部分，范围用于设置起止数字",
                                foreground=self.COLOR_TEXT_SECONDARY, font=self.FONT_SMALL)
            help_text.grid(row=7, column=0, columnspan=2, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            result = {'confirmed': False, 'params': {}}

            def on_confirm():
                try:
                    total = int(total_var.get())
                    start = int(start_var.get())
                    end = int(end_var.get())
                    prefix = prefix_var.get()
                    suffix = suffix_var.get()
                    interval = float(interval_var.get())

                    fixed_len = len(prefix) + len(suffix)
                    if fixed_len >= total:
                        messagebox.showerror("错误", "前缀+后缀长度不能大于等于总位数", parent=self.window)
                        return
                    if len(prefix) + len(suffix) + len(str(start)) > total or len(prefix) + len(suffix) + len(str(end)) > total:
                        messagebox.showerror("错误", "起始或结束数字超出了可表示的范围", parent=self.window)
                        return

                    result['confirmed'] = True
                    result['params'] = {
                        'total_digits': total,
                        'start': start,
                        'end': end,
                        'prefix': prefix,
                        'suffix': suffix,
                        'interval': interval
                    }
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showerror("错误", f"请输入有效的数字: {e}", parent=self.window)

            def on_cancel():
                dialog.destroy()

            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.grid(row=8, column=0, columnspan=2, pady=self.PAD_MD, sticky='ew')

            ttk.Button(btn_frame, text="确定", command=on_confirm).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='left', padx=self.PAD_MD)

            self.window.wait_window(dialog)

            if result['confirmed']:
                params = result['params']
                callback({'type': 'fill', 
                         'total_digits': params['total_digits'],
                         'start': params['start'],
                         'end': params['end'],
                         'prefix': params['prefix'],
                         'suffix': params['suffix'],
                         'interval': params['interval']})
        except Exception as e:
            messagebox.showerror("错误", f"添加填充数字动作时出错: {e}", parent=self.window)
    
    def add_loop_action_sub(self, callback):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("循环控制", 0.55, 0.6)
            
            canvas = tk.Canvas(dialog, borderwidth=0, highlightthickness=0, background=self.COLOR_BG)
            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

            def _on_canvas_configure(event):
                canvas.itemconfig(canvas_window, width=event.width - 4)
            canvas.bind("<Configure>", _on_canvas_configure)

            canvas.configure(yscrollcommand=scrollbar.set)
            
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
            
            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            
            dialog.grid_rowconfigure(0, weight=1)
            dialog.grid_columnconfigure(0, weight=1)
            dialog.grid_columnconfigure(1, weight=0)
            
            ttk.Label(scrollable_frame, text="循环控制设置", font=self.FONT_HEADING).pack(pady=self.PAD_SM)

            param_frame = ttk.LabelFrame(scrollable_frame, text="循环参数", padding=self.PAD_XS)
            param_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            loop_frame = ttk.Frame(param_frame)
            loop_frame.pack(fill='x', pady=self.PAD_XS)
            
            ttk.Label(loop_frame, text="循环次数:").pack(side='left', padx=self.PAD_XS)
            loop_count_var = tk.StringVar(value="-1")
            loop_entry = ttk.Entry(loop_frame, textvariable=loop_count_var, width=10)
            loop_entry.pack(side='left', padx=self.PAD_XS)
            ttk.Label(loop_frame, text="-1表示无限循环", font=self.FONT_NORMAL, foreground=self.COLOR_TEXT_SECONDARY).pack(side='left')

            interval_frame = ttk.Frame(param_frame)
            interval_frame.pack(fill='x', pady=self.PAD_XS)
            
            ttk.Label(interval_frame, text="循环间隔(秒):").pack(side='left', padx=self.PAD_XS)
            loop_interval_var = tk.StringVar(value="0.5")
            interval_spin = ttk.Spinbox(interval_frame, from_=0, to=10, increment=0.1, 
                                       textvariable=loop_interval_var, width=10)
            interval_spin.pack(side='left', padx=self.PAD_XS)

            sub_frame = ttk.LabelFrame(scrollable_frame, text="子动作列表", padding=self.PAD_XS)
            sub_frame.pack(fill='both', expand=True, padx=self.PAD_MD, pady=self.PAD_XS)
            
            sub_tree_container = ttk.Frame(sub_frame)
            sub_tree_container.pack(fill='both', expand=True)
            
            sub_tree = ttk.Treeview(sub_tree_container, columns=('序号', '类型', '参数'), show='headings', height=6)
            sub_tree.heading('序号', text='序号')
            sub_tree.heading('类型', text='类型')
            sub_tree.heading('参数', text='参数')
            
            sub_tree.column('序号', width=50, stretch=False)
            sub_tree.column('类型', width=100, stretch=False)
            sub_tree.column('参数', width=300, stretch=False)
            
            sub_scrollbar_y = ttk.Scrollbar(sub_tree_container, orient="vertical", command=sub_tree.yview)
            sub_tree.configure(yscrollcommand=sub_scrollbar_y.set)
            sub_scrollbar_x = ttk.Scrollbar(sub_tree_container, orient="horizontal", command=sub_tree.xview)
            sub_tree.configure(xscrollcommand=sub_scrollbar_x.set)
            
            sub_tree.grid(row=0, column=0, sticky='nsew')
            sub_scrollbar_y.grid(row=0, column=1, sticky='ns')
            sub_scrollbar_x.grid(row=1, column=0, sticky='ew')
            
            sub_tree_container.grid_rowconfigure(0, weight=1)
            sub_tree_container.grid_columnconfigure(0, weight=1)

            action_display_map = self._get_action_display_map()

            sub_actions_data = []

            def add_sub_action_callback(action_type, action_func):
                def add_action_to_tree(action_params):
                    params_str = ', '.join([f"{k}={v}" for k, v in action_params.items()])
                    display_name = action_display_map.get(action_type, action_type)
                    item_id = sub_tree.insert('', 'end', values=(len(sub_tree.get_children())+1, display_name, params_str))
                    sub_actions_data.append({'item_id': item_id, 'type': action_type, 'params': action_params})
                
                action_func(add_action_to_tree)
            
            btn_frame = ttk.LabelFrame(scrollable_frame, text="添加子动作", padding=self.PAD_XS)
            btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            self.create_action_button_frame(btn_frame, add_sub_action_callback)
            
            edit_btn_frame = ttk.Frame(scrollable_frame)
            edit_btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            def _delete_selected_sub():
                sel = sub_tree.selection()
                if not sel:
                    return
                item_id = sel[0]
                idx = sub_tree.index(item_id)
                sub_tree.delete(item_id)
                if 0 <= idx < len(sub_actions_data):
                    del sub_actions_data[idx]

            def _clear_sub_list():
                sub_tree.delete(*sub_tree.get_children())
                sub_actions_data.clear()

            ttk.Button(edit_btn_frame, text="删除选中", command=_delete_selected_sub).pack(side='left', padx=self.PAD_XS)
            ttk.Button(edit_btn_frame, text="清空列表", command=_clear_sub_list).pack(side='left', padx=self.PAD_XS)

            result = {'confirmed': False, 'params': {}}

            def on_confirm():
                try:
                    count = int(loop_count_var.get())
                    interval = float(loop_interval_var.get())
                    
                    sub_actions = []
                    for data in sub_actions_data:
                        kwargs = {k: v for k, v in data['params'].items() if k != 'type'}
                        sub_actions.append({'type': data['type'], 'kwargs': kwargs})

                    result['confirmed'] = True
                    result['params'] = {
                        'repeat': count,
                        'interval': interval,
                        'sub_actions': sub_actions
                    }
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showerror("错误", f"请输入有效的数字: {e}", parent=self.window)

            def on_cancel():
                dialog.destroy()
            
            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.pack(pady=self.PAD_SM)

            ttk.Button(btn_frame, text="确定", command=on_confirm, width=12).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel, width=12).pack(side='left', padx=self.PAD_MD)

            self.window.wait_window(dialog)
            
            if result['confirmed']:
                callback({'type': 'loop', **result['params']})
        except Exception as e:
            messagebox.showerror("错误", f"添加循环控制时出错: {e}", parent=self.window)
    
    def add_conditional_action_sub(self, callback):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("条件控制", 0.55, 0.65)
            
            canvas = tk.Canvas(dialog, borderwidth=0, highlightthickness=0, background=self.COLOR_BG)
            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

            def _on_canvas_configure(event):
                canvas.itemconfig(canvas_window, width=event.width - 4)
            canvas.bind("<Configure>", _on_canvas_configure)

            canvas.configure(yscrollcommand=scrollbar.set)
            
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
            
            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            
            dialog.grid_rowconfigure(0, weight=1)
            dialog.grid_columnconfigure(0, weight=1)
            dialog.grid_columnconfigure(1, weight=0)
            
            ttk.Label(scrollable_frame, text="条件控制设置", font=self.FONT_HEADING).pack(pady=self.PAD_SM)

            type_frame = ttk.LabelFrame(scrollable_frame, text="条件类型", padding=self.PAD_XS)
            type_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            ttk.Label(type_frame, text="检测类型:").pack(side='left', padx=self.PAD_XS)
            
            cond_options = [
                ("键盘按键", "keyboard"), ("移动鼠标", "move"), ("图像识别点击", "locate_click"), ("鼠标点击", "click"),
                ("鼠标双击", "double_click"), ("右键点击", "right_click"), ("左键点击", "left_click"),
                ("滚轮滚动", "scroll"), ("按键", "press"), ("输入文本", "type"),
                ("快捷键", "hotkey"), ("鼠标长按", "hold"),
                ("键盘长按", "key_hold"), ("多按键同步", "multi_key"), ("多鼠标同步", "multi_mouse"),
                ("键盘鼠标同步", "multi_key_mouse"), ("填充数字", "fill"),
                ("打开文件", "open_file"), ("打开网站", "open_url"),
                ("文本输入监听", "type"),
                ("数字填充监听", "fill"),
                ("文件变化监听", "open_file_listen"),
                ("剪贴板URL监听", "open_url_listen"),
                ("浏览器网页监听", "browser_open"),
                ("多键同时按下", "multi_key"),
                ("多鼠标事件组合", "multi_mouse"),
                ("键鼠组合监听", "multi_key_mouse"),
            ]
            cond_type_map = {label: value for label, value in cond_options}
            
            cond_type_var = tk.StringVar(value="keyboard")
            cond_type_combo = ttk.Combobox(type_frame, values=[label for label, _ in cond_options],
                                           width=18, state="readonly")
            cond_type_combo.pack(side='left', padx=self.PAD_MD)
            cond_type_combo.current(0)
            
            param_frame = ttk.LabelFrame(scrollable_frame, text="触发参数", padding=self.PAD_XS)
            param_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            cond_target_var = tk.StringVar(value="f1")
            cond_x_var = tk.StringVar(value="0")
            cond_y_var = tk.StringVar(value="0")
            cond_btn_var = tk.StringVar(value="left")
            cond_dir_var = tk.StringVar(value="向上")
            cond_dur_var = tk.StringVar(value="1")
            
            def build_sub_param_ui():
                for w in param_frame.winfo_children():
                    w.destroy()
                selected_label = cond_type_combo.get()
                ctype = cond_type_map.get(selected_label, "keyboard")
                cond_type_var.set(ctype)
                
                if ctype in ('keyboard', 'press', 'key_hold'):
                    ttk.Label(param_frame, text="触发按键:").pack(anchor='w')
                    key_row = ttk.Frame(param_frame)
                    key_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Entry(key_row, textvariable=cond_target_var, width=15, state='readonly').pack(side='left')
                    ttk.Button(key_row, text="选择按键",
                              command=lambda: cond_target_var.set(self.select_key_dialog("选择触发按键") or cond_target_var.get())).pack(side='left', padx=self.PAD_XS)
                    if ctype == 'key_hold':
                        ttk.Label(param_frame, text="长按时长(秒):").pack(anchor='w', pady=(self.PAD_XS, 0))
                        ttk.Entry(param_frame, textvariable=cond_dur_var, width=10).pack(anchor='w')
                elif ctype in ('click', 'double_click', 'hold'):
                    ttk.Label(param_frame, text="鼠标按钮:").pack(anchor='w')
                    btn_row = ttk.Frame(param_frame)
                    btn_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Combobox(btn_row, values=["left", "right", "middle"],
                                textvariable=cond_btn_var, width=12, state="readonly").pack(side='left')
                    if ctype == 'hold':
                        ttk.Label(param_frame, text="长按时长(秒):").pack(anchor='w', pady=(self.PAD_XS, 0))
                        ttk.Entry(param_frame, textvariable=cond_dur_var, width=10).pack(anchor='w')
                elif ctype in ('right_click', 'left_click'):
                    fixed_btn = "右键" if ctype == 'right_click' else "左键"
                    ttk.Label(param_frame, text=f"固定按钮: {fixed_btn}").pack(anchor='w')
                    cond_btn_var.set('right' if ctype == 'right_click' else 'left')
                elif ctype == 'move':
                    ttk.Label(param_frame, text="目标坐标:").pack(anchor='w')
                    coord_row = ttk.Frame(param_frame)
                    coord_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(coord_row, text="X:").pack(side='left')
                    ttk.Entry(coord_row, textvariable=cond_x_var, width=8).pack(side='left', padx=self.PAD_XS)
                    ttk.Label(coord_row, text="Y:").pack(side='left')
                    ttk.Entry(coord_row, textvariable=cond_y_var, width=8).pack(side='left', padx=self.PAD_XS)
                    ttk.Button(coord_row, text="获取当前位置",
                              command=lambda: (cond_x_var.set(str(self.autoclicker.get_current_position().x)),
                                             cond_y_var.set(str(self.autoclicker.get_current_position().y)))).pack(side='left', padx=self.PAD_XS)
                elif ctype == 'scroll':
                    ttk.Label(param_frame, text="滚动方向:").pack(anchor='w')
                    ttk.Combobox(param_frame, values=["向上", "向下", "向左", "向右"],
                                textvariable=cond_dir_var, width=12, state="readonly").pack(anchor='w', pady=(0, self.PAD_XS))
                elif ctype == 'hotkey':
                    ttk.Label(param_frame, text="快捷键组合(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=25).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: ctrl+c, alt+tab, shift+f1", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'type':
                    ttk.Label(param_frame, text="检测文本(剪贴板包含此文本时触发):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="监听剪贴板变化，匹配到指定文本后触发", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'fill':
                    ttk.Label(param_frame, text="检测到剪贴板为纯数字时触发").pack(anchor='w')
                    ttk.Label(param_frame, text="监听剪贴板变化，检测到纯数字内容后触发", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'open_file_listen':
                    ttk.Label(param_frame, text="监听文件路径:").pack(anchor='w')
                    file_row = ttk.Frame(param_frame)
                    file_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Entry(file_row, textvariable=cond_target_var, width=30).pack(side='left')
                    def browse_file():
                        fp = filedialog.askopenfilename(title="选择监听文件", parent=self.window)
                        if fp:
                            cond_target_var.set(fp)
                    ttk.Button(file_row, text="浏览", command=browse_file).pack(side='left', padx=self.PAD_XS)
                    cond_dir_var.set("exists")
                    ttk.Label(param_frame, text="检测模式:").pack(anchor='w', pady=(self.PAD_XS, 0))
                    ttk.Combobox(param_frame, values=["文件出现(存在)", "文件修改(时间变化)"],
                                 textvariable=cond_dir_var, width=20, state="readonly").pack(anchor='w')
                elif ctype == 'open_url_listen':
                    ttk.Label(param_frame, text="检测URL关键词(剪贴板包含时触发):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: baidu.com, taobao.com", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'browser_open':
                    ttk.Label(param_frame, text="检测浏览器窗口标题包含:").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="检测所有可见窗口标题，包含关键词时触发", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                    ttk.Label(param_frame, text="例: 百度, Baidu, taobao, 淘宝", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'multi_key':
                    ttk.Label(param_frame, text="同时按下的按键(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: ctrl+shift+a", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'multi_mouse':
                    ttk.Label(param_frame, text="鼠标事件组合(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: left+double, right+scroll", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'multi_key_mouse':
                    ttk.Label(param_frame, text="键鼠组合事件(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: ctrl+left_click, shift+double_click", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
            
            cond_type_combo.bind("<<ComboboxSelected>>", lambda e: build_sub_param_ui())
            build_sub_param_ui()

            multi_frame = ttk.LabelFrame(scrollable_frame, text="触发条件（支持多个）", padding=self.PAD_XS)
            multi_frame.pack(fill='both', expand=True, padx=self.PAD_MD, pady=self.PAD_XS)
            
            tree_container = ttk.Frame(multi_frame)
            tree_container.pack(fill='both', expand=True)
            
            condition_tree = ttk.Treeview(tree_container, columns=('序号', '类型', '按键'), show='headings', height=5)
            condition_tree.heading('序号', text='序号')
            condition_tree.heading('类型', text='类型')
            condition_tree.heading('按键', text='按键')
            
            condition_tree.column('序号', width=50, stretch=False)
            condition_tree.column('类型', width=80, stretch=False)
            condition_tree.column('按键', width=200, stretch=False)
            
            cond_scrollbar_y = ttk.Scrollbar(tree_container, orient="vertical", command=condition_tree.yview)
            condition_tree.configure(yscrollcommand=cond_scrollbar_y.set)
            cond_scrollbar_x = ttk.Scrollbar(tree_container, orient="horizontal", command=condition_tree.xview)
            condition_tree.configure(xscrollcommand=cond_scrollbar_x.set)
            
            condition_tree.grid(row=0, column=0, sticky='nsew')
            cond_scrollbar_y.grid(row=0, column=1, sticky='ns')
            cond_scrollbar_x.grid(row=1, column=0, sticky='ew')
            
            tree_container.grid_rowconfigure(0, weight=1)
            tree_container.grid_columnconfigure(0, weight=1)

            def add_condition():
                ctype = cond_type_var.get()
                cond_type_label = cond_type_combo.get()
                
                if ctype in ('keyboard', 'press'):
                    keys = self.select_multi_keys_dialog("选择触发按键")
                    for key in keys:
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, key))
                elif ctype == 'key_hold':
                    key = self.select_key_dialog("选择长按按键")
                    if key:
                        dur = cond_dur_var.get()
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"{key} ({dur}秒)"))
                elif ctype in ('click', 'double_click', 'hold'):
                    btn = cond_btn_var.get()
                    if ctype == 'hold':
                        dur = cond_dur_var.get()
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"{btn} ({dur}秒)"))
                    else:
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, btn))
                elif ctype in ('right_click', 'left_click'):
                    btn = '右键' if ctype == 'right_click' else '左键'
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, btn))
                elif ctype == 'move':
                    x, y = cond_x_var.get(), cond_y_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"({x}, {y})"))
                elif ctype == 'scroll':
                    direction = cond_dir_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, direction))
                elif ctype == 'hotkey':
                    hk = simpledialog.askstring("快捷键", "输入快捷键组合(如 ctrl+c):", parent=self.window)
                    if hk:
                        cond_target_var.set(hk)
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, hk))
                elif ctype == 'type':
                    txt = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, txt))
                elif ctype == 'fill':
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, "纯数字"))
                elif ctype == 'open_file_listen':
                    fp = cond_target_var.get()
                    mode = cond_dir_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"{fp} [{mode}]"))
                elif ctype == 'open_url_listen':
                    kw = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, kw))
                elif ctype == 'browser_open':
                    kw = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, kw))
                elif ctype in ('multi_key', 'multi_mouse', 'multi_key_mouse'):
                    combo = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, combo))
            
            btn_frame1 = ttk.Frame(scrollable_frame)
            btn_frame1.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            ttk.Button(btn_frame1, text="添加条件", command=add_condition).pack(side='left', padx=self.PAD_XS)
            ttk.Button(btn_frame1, text="删除选中", command=lambda: condition_tree.delete(condition_tree.selection()[0] if condition_tree.selection() else None)).pack(side='left', padx=self.PAD_XS)
            ttk.Button(btn_frame1, text="清空列表", command=lambda: [condition_tree.delete(item) for item in condition_tree.get_children()]).pack(side='left', padx=self.PAD_XS)

            sub_frame = ttk.LabelFrame(scrollable_frame, text="触发后执行的子动作", padding=self.PAD_XS)
            sub_frame.pack(fill='both', expand=True, padx=self.PAD_MD, pady=self.PAD_XS)
            
            sub_tree_container = ttk.Frame(sub_frame)
            sub_tree_container.pack(fill='both', expand=True)
            
            sub_tree = ttk.Treeview(sub_tree_container, columns=('序号', '类型', '参数'), show='headings', height=6)
            sub_tree.heading('序号', text='序号')
            sub_tree.heading('类型', text='类型')
            sub_tree.heading('参数', text='参数')
            
            sub_tree.column('序号', width=50, stretch=False)
            sub_tree.column('类型', width=100, stretch=False)
            sub_tree.column('参数', width=300, stretch=False)
            
            sub_scrollbar_y = ttk.Scrollbar(sub_tree_container, orient="vertical", command=sub_tree.yview)
            sub_tree.configure(yscrollcommand=sub_scrollbar_y.set)
            sub_scrollbar_x = ttk.Scrollbar(sub_tree_container, orient="horizontal", command=sub_tree.xview)
            sub_tree.configure(xscrollcommand=sub_scrollbar_x.set)
            
            sub_tree.grid(row=0, column=0, sticky='nsew')
            sub_scrollbar_y.grid(row=0, column=1, sticky='ns')
            sub_scrollbar_x.grid(row=1, column=0, sticky='ew')
            
            sub_tree_container.grid_rowconfigure(0, weight=1)
            sub_tree_container.grid_columnconfigure(0, weight=1)

            action_display_map = self._get_action_display_map()

            sub_actions_data = []

            def add_sub_action_callback(action_type, action_func):
                def add_action_to_tree(action_params):
                    params_str = ', '.join([f"{k}={v}" for k, v in action_params.items()])
                    display_name = action_display_map.get(action_type, action_type)
                    item_id = sub_tree.insert('', 'end', values=(len(sub_tree.get_children())+1, display_name, params_str))
                    sub_actions_data.append({'item_id': item_id, 'type': action_type, 'params': action_params})
                action_func(add_action_to_tree)
            
            btn_frame = ttk.LabelFrame(scrollable_frame, text="添加子动作", padding=self.PAD_XS)
            btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            self.create_action_button_frame(btn_frame, add_sub_action_callback)
            
            edit_btn_frame = ttk.Frame(scrollable_frame)
            edit_btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            def _delete_selected_sub():
                sel = sub_tree.selection()
                if not sel:
                    return
                item_id = sel[0]
                idx = sub_tree.index(item_id)
                sub_tree.delete(item_id)
                if 0 <= idx < len(sub_actions_data):
                    del sub_actions_data[idx]

            def _clear_sub_list():
                sub_tree.delete(*sub_tree.get_children())
                sub_actions_data.clear()

            ttk.Button(edit_btn_frame, text="删除选中", command=_delete_selected_sub).pack(side='left', padx=self.PAD_XS)
            ttk.Button(edit_btn_frame, text="清空列表", command=_clear_sub_list).pack(side='left', padx=self.PAD_XS)
            
            result = {'confirmed': False, 'params': {}}

            def on_confirm():
                condition_type = cond_type_var.get()
                
                conditions = []
                for item in condition_tree.get_children():
                    values = condition_tree.item(item)['values']
                    conditions.append(values[2])
                
                sub_actions = []
                for data in sub_actions_data:
                    kwargs = {k: v for k, v in data['params'].items() if k != 'type'}
                    sub_actions.append({'type': data['type'], 'kwargs': kwargs})

                if not conditions:
                    messagebox.showerror("错误", "请至少添加一个触发条件", parent=self.window)
                    return
                
                params = {
                    'condition_type': condition_type,
                    'target_keys': conditions,
                    'sub_actions': sub_actions
                }
                
                if condition_type == 'move' and conditions:
                    try:
                        coord_str = conditions[0].strip("()")
                        x, y = coord_str.split(",")
                        params['target_x'] = int(x.strip())
                        params['target_y'] = int(y.strip())
                    except:
                        pass
                elif condition_type in ('hold', 'key_hold'):
                    params['duration'] = float(cond_dur_var.get() or 1)
                elif condition_type == 'type':
                    params['target_key'] = cond_target_var.get()
                elif condition_type == 'fill':
                    pass
                elif condition_type == 'open_file_listen':
                    params['target_key'] = cond_target_var.get()
                    mode_map = {"文件出现(存在)": "exists", "文件修改(时间变化)": "modified"}
                    params['monitor_mode'] = mode_map.get(cond_dir_var.get(), "exists")
                elif condition_type == 'open_url_listen':
                    params['target_key'] = cond_target_var.get()
                elif condition_type == 'browser_open':
                    params['target_key'] = cond_target_var.get()
                elif condition_type in ('multi_key', 'multi_mouse', 'multi_key_mouse'):
                    params['target_key'] = cond_target_var.get()
                
                result['confirmed'] = True
                result['params'] = params
                dialog.destroy()

            def on_cancel():
                dialog.destroy()
            
            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.pack(pady=self.PAD_SM)

            ttk.Button(btn_frame, text="确定", command=on_confirm, width=12).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel, width=12).pack(side='left', padx=self.PAD_MD)

            self.window.wait_window(dialog)
            
            if result['confirmed']:
                callback({'type': 'conditional', **result['params']})
        except Exception as e:
            messagebox.showerror("错误", f"添加条件控制时出错: {e}", parent=self.window)
    
    def add_drag_action(self, insert_index=None):
        try:
            dialog = tk.Toplevel(self.window)
            dialog.title("添加拖拽")
            dialog.transient(self.window)
            dialog.grab_set()
            dialog.resizable(False, False)

            main = ttk.Frame(dialog, padding=15)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text="鼠标拖拽", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))

            ttk.Label(main, text="坐标类型: 屏幕坐标（相对屏幕左上角）", foreground='#0078D4',
                      font=("Microsoft YaHei UI", 9, "italic")).pack(anchor='w', pady=(0, 8))

            coord_frame = ttk.Frame(main)
            coord_frame.pack(fill='x', pady=5)
            ttk.Label(coord_frame, text="X 目标:").grid(row=0, column=0, sticky='w', padx=(0, 5))
            x_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=x_var, width=10).grid(row=0, column=1, padx=(0, 15))
            ttk.Label(coord_frame, text="Y 目标:").grid(row=0, column=2, sticky='w', padx=(0, 5))
            y_var = tk.IntVar(value=0)
            ttk.Entry(coord_frame, textvariable=y_var, width=10).grid(row=0, column=3)

            btn_row = ttk.Frame(main)
            btn_row.pack(fill='x', pady=5)
            def get_pos():
                pos = self.autoclicker.get_current_position()
                x_var.set(pos.x)
                y_var.set(pos.y)
            ttk.Button(btn_row, text="获取当前鼠标位置 (F2)", command=get_pos).pack(side='left', padx=(0, 10))

            if self.position_cache:
                cache_items = [f"[{p['time']}] X={p['x']}, Y={p['y']}" for p in self.position_cache]
                def on_cache_select(*args):
                    sel = cache_combo.current()
                    if sel >= 0:
                        p = self.position_cache[sel]
                        x_var.set(p['x'])
                        y_var.set(p['y'])
                ttk.Label(btn_row, text="F2记录:").pack(side='left')
                cache_combo = ttk.Combobox(btn_row, values=cache_items, width=22, state="readonly")
                cache_combo.pack(side='left', padx=(5, 0))
                cache_combo.bind("<<ComboboxSelected>>", on_cache_select)

            dur_frame = ttk.Frame(main)
            dur_frame.pack(fill='x', pady=5)
            ttk.Label(dur_frame, text="拖拽时间(秒, 0=瞬移):").pack(side='left')
            dur_var = tk.StringVar(value="0")
            ttk.Entry(dur_frame, textvariable=dur_var, width=8).pack(side='left', padx=(5, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            ttk.Button(main, text="确定", command=on_ok).pack(side='right', padx=5, pady=(10, 0))
            ttk.Button(main, text="取消", command=lambda: dialog.destroy()).pack(side='right', pady=(10, 0))

            self.window.wait_window(dialog)
            if not result['ok']:
                return
            self._add_or_insert_action(insert_index, 'drag', x=x_var.get(), y=y_var.get(),
                                       duration=float(dur_var.get()))
            self.update_action_list()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字", parent=self.window)
    
    def add_scroll_action(self, insert_index=None):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("鼠标滚轮控制", 0.5, 0.4)
            
            ttk.Label(dialog, text="滚轮滚动设置", font=self.FONT_HEADING).pack(pady=self.PAD_MD)
            
            direction_frame = ttk.Frame(dialog)
            direction_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(direction_frame, text="滚动方向:").pack(side='left', padx=self.PAD_XS)
            direction_var = tk.StringVar(value="up")
            direction_frame2 = ttk.Frame(direction_frame)
            direction_frame2.pack(side='left', padx=self.PAD_XS)
            ttk.Radiobutton(direction_frame2, text="向上", variable=direction_var, value="up").pack(side='left', padx=self.PAD_XS)
            ttk.Radiobutton(direction_frame2, text="向下", variable=direction_var, value="down").pack(side='left', padx=self.PAD_XS)
            ttk.Label(direction_frame, text="   ").pack(side='left')
            ttk.Radiobutton(direction_frame, text="向左", variable=direction_var, value="left").pack(side='left', padx=self.PAD_XS)
            ttk.Radiobutton(direction_frame, text="向右", variable=direction_var, value="right").pack(side='left', padx=self.PAD_XS)
            
            amount_frame = ttk.Frame(dialog)
            amount_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(amount_frame, text="滚动量:").pack(side='left', padx=self.PAD_XS)
            amount_var = tk.IntVar(value=10)
            amount_label = ttk.Label(amount_frame, text="10", width=4)
            amount_label.pack(side='left', padx=self.PAD_XS)
            
            def update_amount_label(val):
                amount_label.config(text=str(int(float(val))))
            
            amount_scale = tk.Scale(amount_frame, from_=1, to=100, orient='horizontal', 
                                   variable=amount_var, length=200, showvalue=0,
                                   command=update_amount_label)
            amount_scale.pack(side='left', padx=self.PAD_MD)
            
            speed_frame = ttk.Frame(dialog)
            speed_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(speed_frame, text="滚动间隔:").pack(side='left', padx=self.PAD_XS)
            speed_var = tk.DoubleVar(value=0.1)
            speed_label = ttk.Label(speed_frame, text="0.1", width=6)
            speed_label.pack(side='left', padx=self.PAD_XS)
            
            def update_speed_label(val):
                speed_label.config(text=f"{float(val):.1f}")
            
            speed_scale = tk.Scale(speed_frame, from_=0, to=2, orient='horizontal', 
                                  variable=speed_var, resolution=0.1, length=200, showvalue=0,
                                  command=update_speed_label)
            speed_scale.pack(side='left', padx=self.PAD_MD)
            ttk.Label(speed_frame, text="秒（0为连续滚动）").pack(side='left', padx=self.PAD_XS)
            
            repeat_frame = ttk.Frame(dialog)
            repeat_frame.pack(fill='x', padx=self.PAD_LG, pady=self.PAD_MD)
            
            ttk.Label(repeat_frame, text="重复次数:").pack(side='left', padx=self.PAD_XS)
            repeat_var = tk.IntVar(value=1)
            repeat_label = ttk.Label(repeat_frame, text="1", width=4)
            repeat_label.pack(side='left', padx=self.PAD_XS)
            
            def update_repeat_label(val):
                repeat_label.config(text=str(int(float(val))))
            
            repeat_scale = tk.Scale(repeat_frame, from_=1, to=50, orient='horizontal',
                                   variable=repeat_var, length=200, showvalue=0,
                                   command=update_repeat_label)
            repeat_scale.pack(side='left', padx=self.PAD_MD)
            ttk.Label(repeat_frame, text="次").pack(side='left', padx=self.PAD_XS)
            
            result = {'confirmed': False, 'params': {}}
            
            def on_confirm():
                try:
                    direction = direction_var.get()
                    amount = amount_var.get()
                    interval = speed_var.get()
                    repeat = repeat_var.get()
                    
                    if direction == "up":
                        clicks = amount
                        scroll_direction = 'vertical'
                    elif direction == "down":
                        clicks = -amount
                        scroll_direction = 'vertical'
                    elif direction == "left":
                        clicks = -amount
                        scroll_direction = 'horizontal'
                    else:
                        clicks = amount
                        scroll_direction = 'horizontal'
                    
                    result['confirmed'] = True
                    result['params'] = {
                        'clicks': clicks,
                        'direction': scroll_direction,
                        'amount': amount,
                        'interval': interval,
                        'repeat': repeat
                    }
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showerror("错误", f"请输入有效的数字: {e}", parent=self.window)
            
            def on_cancel():
                dialog.destroy()
            
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=self.PAD_MD)
            
            ttk.Button(btn_frame, text="确定", command=on_confirm).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='left', padx=self.PAD_MD)
            
            self.window.wait_window(dialog)
            
            if result['confirmed']:
                params = result['params']
                cur_idx = insert_index
                for i in range(params['repeat']):
                    self._add_or_insert_action(cur_idx, 'scroll',
                                                         clicks=params['clicks'],
                                                         direction=params['direction'])
                    if cur_idx is not None:
                        cur_idx += 1
                    if params['interval'] > 0 and i < params['repeat'] - 1:
                        self._add_or_insert_action(cur_idx, 'wait', wait_type='time', seconds=params['interval'], timeout=30)
                        if cur_idx is not None:
                            cur_idx += 1
                self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加滚动动作时出错: {e}", parent=self.window)
    
    def add_hold_action(self, insert_index=None):
        try:
            button_type = simpledialog.askstring("按钮类型", "按钮类型(left/right):", 
                                               parent=self.window, initialvalue="left")
            if button_type not in ['left', 'right']:
                messagebox.showerror("错误", "按钮类型只能是 left 或 right", parent=self.window)
                return
                
            duration = simpledialog.askfloat("长按时间", "长按时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if duration:
                action = self._add_or_insert_action(insert_index, 'hold', button=button_type, duration=duration)
                self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加长按动作时出错: {e}", parent=self.window)
    
    def add_key_hold_action(self, insert_index=None):
        try:
            key = self.select_key_dialog("添加键盘长按")
            if not key:
                return
                
            duration = simpledialog.askfloat("长按时间", "长按时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if duration:
                action = self._add_or_insert_action(insert_index, 'key_hold', key=key, duration=duration)
                self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加键盘长按动作时出错: {e}", parent=self.window)
    
    def add_multi_key_action(self, insert_index=None):
        try:
            self.window.lift()
            self.window.focus_force()
            
            keys = self.select_multi_keys_dialog("多按键同步")
            if not keys:
                return
            
            self.window.lift()
            
            duration = simpledialog.askfloat("持续时间", "持续时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if not duration:
                return
                
            action = self._add_or_insert_action(insert_index, 'multi_key', keys=keys, duration=duration)
            self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加多按键同步动作时出错: {e}", parent=self.window)
    
    def add_multi_mouse_action(self, insert_index=None):
        try:
            self.window.lift()
            self.window.focus_force()
            
            buttons_input = simpledialog.askstring("多鼠标按键同步", "鼠标按键(left,right,middle):", 
                                               parent=self.window, initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            self.window.lift()
            
            duration = simpledialog.askfloat("持续时间", "持续时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if not duration:
                return
                
            action = self._add_or_insert_action(insert_index, 'multi_mouse', buttons=buttons, duration=duration)
            self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加多鼠标按键同步动作时出错: {e}", parent=self.window)
    
    def add_multi_key_mouse_action(self, insert_index=None):
        try:
            self.window.lift()
            self.window.focus_force()
            
            keys = self.select_multi_keys_dialog("选择键盘按键")
            if not keys:
                return
            
            self.window.lift()
            
            buttons_input = simpledialog.askstring("鼠标按键", "鼠标按键(left,right,middle):", 
                                                 parent=self.window, initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            self.window.lift()
            
            duration = simpledialog.askfloat("持续时间", "持续时间(秒):", 
                                           parent=self.window, initialvalue=1.0)
            if not duration:
                return
                
            action = self._add_or_insert_action(insert_index, 'multi_key_mouse', keys=keys, buttons=buttons, duration=duration)
            self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加键盘与鼠标同步动作时出错: {e}", parent=self.window)

    def move_up_action(self):
        index = self.get_selected_index()
        if index is None or index == 0:
            return
        
        self.autoclicker.actions[index], self.autoclicker.actions[index-1] = \
            self.autoclicker.actions[index-1], self.autoclicker.actions[index]
        self.update_action_list()
        self.tree.selection_set(self.tree.get_children()[index-1])
    
    def move_down_action(self):
        index = self.get_selected_index()
        if index is None or index == len(self.autoclicker.actions) - 1:
            return
        
        self.autoclicker.actions[index], self.autoclicker.actions[index+1] = \
            self.autoclicker.actions[index+1], self.autoclicker.actions[index]
        self.update_action_list()
        self.tree.selection_set(self.tree.get_children()[index+1])

    def add_loop_action(self, insert_index=None):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("循环控制设置", 0.55, 0.8)
            
            canvas = tk.Canvas(dialog, borderwidth=0, highlightthickness=0, background=self.COLOR_BG)
            main_scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

            def _on_canvas_configure(event):
                canvas.itemconfig(canvas_window, width=event.width - 4)
            canvas.bind("<Configure>", _on_canvas_configure)

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

            canvas.configure(yscrollcommand=main_scrollbar.set)

            canvas.grid(row=0, column=0, sticky="nsew")
            main_scrollbar.grid(row=0, column=1, sticky="ns")

            dialog.grid_rowconfigure(0, weight=1)
            dialog.grid_columnconfigure(0, weight=1)
            dialog.grid_columnconfigure(1, weight=0)

            ttk.Label(scrollable_frame, text="循环控制设置", font=self.FONT_HEADING).pack(pady=self.PAD_SM)

            param_frame = ttk.LabelFrame(scrollable_frame, text="循环参数", padding=self.PAD_XS)
            param_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            loop_frame = ttk.Frame(param_frame)
            loop_frame.pack(fill='x', pady=self.PAD_XS)
            
            ttk.Label(loop_frame, text="循环次数:").pack(side='left', padx=self.PAD_XS)
            loop_count_var = tk.StringVar(value="-1")
            loop_entry = ttk.Entry(loop_frame, textvariable=loop_count_var, width=10)
            loop_entry.pack(side='left', padx=self.PAD_XS)
            ttk.Label(loop_frame, text="-1表示无限循环", font=self.FONT_NORMAL, foreground=self.COLOR_TEXT_SECONDARY).pack(side='left')

            interval_frame = ttk.Frame(param_frame)
            interval_frame.pack(fill='x', pady=self.PAD_XS)
            
            ttk.Label(interval_frame, text="循环间隔(秒):").pack(side='left', padx=self.PAD_XS)
            loop_interval_var = tk.StringVar(value="0.5")
            interval_spin = ttk.Spinbox(interval_frame, from_=0, to=10, increment=0.1, 
                                       textvariable=loop_interval_var, width=10)
            interval_spin.pack(side='left', padx=self.PAD_XS)

            sub_frame = ttk.LabelFrame(scrollable_frame, text="子动作列表", padding=self.PAD_XS)
            sub_frame.pack(fill='both', expand=True, padx=self.PAD_MD, pady=self.PAD_XS)
            
            sub_tree_container = ttk.Frame(sub_frame)
            sub_tree_container.pack(fill='both', expand=True)
            
            sub_tree = ttk.Treeview(sub_tree_container, columns=('序号', '类型', '参数'), show='headings', height=8)
            sub_tree.heading('序号', text='序号')
            sub_tree.heading('类型', text='类型')
            sub_tree.heading('参数', text='参数')
            
            sub_tree.column('序号', width=50, stretch=False)
            sub_tree.column('类型', width=100, stretch=False)
            sub_tree.column('参数', width=300, stretch=False)
            
            sub_scrollbar_y = ttk.Scrollbar(sub_tree_container, orient="vertical", command=sub_tree.yview)
            sub_tree.configure(yscrollcommand=sub_scrollbar_y.set)
            sub_scrollbar_x = ttk.Scrollbar(sub_tree_container, orient="horizontal", command=sub_tree.xview)
            sub_tree.configure(xscrollcommand=sub_scrollbar_x.set)
            
            sub_tree.grid(row=0, column=0, sticky='nsew')
            sub_scrollbar_y.grid(row=0, column=1, sticky='ns')
            sub_scrollbar_x.grid(row=1, column=0, sticky='ew')
            
            sub_tree_container.grid_rowconfigure(0, weight=1)
            sub_tree_container.grid_columnconfigure(0, weight=1)

            action_display_map = self._get_action_display_map()

            sub_actions_data = []

            def add_sub_action_callback(action_type, action_func):
                def add_action_to_tree(action_params):
                    params_str = ', '.join([f"{k}={v}" for k, v in action_params.items()])
                    display_name = action_display_map.get(action_type, action_type)
                    item_id = sub_tree.insert('', 'end', values=(len(sub_tree.get_children())+1, display_name, params_str))
                    sub_actions_data.append({'item_id': item_id, 'type': action_type, 'params': action_params})
                
                action_func(add_action_to_tree)
            
            btn_frame = ttk.LabelFrame(scrollable_frame, text="添加子动作", padding=self.PAD_XS)
            btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            self.create_action_button_frame(btn_frame, add_sub_action_callback)
            
            edit_btn_frame = ttk.Frame(scrollable_frame)
            edit_btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            def _delete_selected_sub():
                sel = sub_tree.selection()
                if not sel:
                    return
                item_id = sel[0]
                idx = sub_tree.index(item_id)
                sub_tree.delete(item_id)
                if 0 <= idx < len(sub_actions_data):
                    del sub_actions_data[idx]

            def _clear_sub_list():
                sub_tree.delete(*sub_tree.get_children())
                sub_actions_data.clear()

            ttk.Button(edit_btn_frame, text="删除选中", command=_delete_selected_sub).pack(side='left', padx=self.PAD_XS)
            ttk.Button(edit_btn_frame, text="清空列表", command=_clear_sub_list).pack(side='left', padx=self.PAD_XS)

            result = {'confirmed': False, 'params': {}}

            def on_confirm():
                try:
                    count = int(loop_count_var.get())
                    interval = float(loop_interval_var.get())
                    
                    sub_actions = []
                    for data in sub_actions_data:
                        kwargs = {k: v for k, v in data['params'].items() if k != 'type'}
                        sub_actions.append({'type': data['type'], 'kwargs': kwargs})

                    result['confirmed'] = True
                    result['params'] = {
                        'repeat': count,
                        'interval': interval,
                        'sub_actions': sub_actions
                    }
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showerror("错误", f"请输入有效的数字: {e}", parent=self.window)

            def on_cancel():
                dialog.destroy()

            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.pack(pady=self.PAD_SM)

            ttk.Button(btn_frame, text="确定", command=on_confirm, width=12).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel, width=12).pack(side='left', padx=self.PAD_MD)

            self.window.wait_window(dialog)

            if result['confirmed']:
                params = result['params']
                self._add_or_insert_action(insert_index, 'loop', **params)
                self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加循环控制动作时出错: {e}", parent=self.window)

    def add_conditional_action(self, insert_index=None):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("条件控制设置", 0.55, 0.85)
            
            canvas = tk.Canvas(dialog, borderwidth=0, highlightthickness=0, background=self.COLOR_BG)
            main_scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
            
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=main_scrollbar.set)
            
            def _on_canvas_configure(event):
                canvas.itemconfig(canvas_window, width=event.width - 4)
            canvas.bind("<Configure>", _on_canvas_configure)
            
            canvas.grid(row=0, column=0, sticky="nsew")
            main_scrollbar.grid(row=0, column=1, sticky="ns")
            
            dialog.grid_rowconfigure(0, weight=1)
            dialog.grid_columnconfigure(0, weight=1)
            
            
            ttk.Label(scrollable_frame, text="条件控制设置", font=self.FONT_HEADING).pack(pady=self.PAD_SM)

            type_frame = ttk.LabelFrame(scrollable_frame, text="条件类型", padding=self.PAD_XS)
            type_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            ttk.Label(type_frame, text="检测类型:").pack(side='left', padx=self.PAD_XS)
            
            cond_options = [
                ("键盘按键", "keyboard"), ("移动鼠标", "move"), ("图像识别点击", "locate_click"), ("鼠标点击", "click"),
                ("鼠标双击", "double_click"), ("右键点击", "right_click"), ("左键点击", "left_click"),
                ("滚轮滚动", "scroll"), ("按键", "press"), ("输入文本", "type"),
                ("快捷键", "hotkey"), ("鼠标长按", "hold"),
                ("键盘长按", "key_hold"), ("多按键同步", "multi_key"), ("多鼠标同步", "multi_mouse"),
                ("键盘鼠标同步", "multi_key_mouse"), ("填充数字", "fill"),
                ("打开文件", "open_file"), ("打开网站", "open_url"),
                ("文本输入监听", "type"),
                ("数字填充监听", "fill"),
                ("文件变化监听", "open_file_listen"),
                ("剪贴板URL监听", "open_url_listen"),
                ("浏览器网页监听", "browser_open"),
                ("多键同时按下", "multi_key"),
                ("多鼠标事件组合", "multi_mouse"),
                ("键鼠组合监听", "multi_key_mouse"),
            ]
            cond_type_map = {label: value for label, value in cond_options}
            
            cond_type_var = tk.StringVar(value="keyboard")
            cond_type_combo = ttk.Combobox(type_frame, values=[label for label, _ in cond_options],
                                           width=18, state="readonly")
            cond_type_combo.pack(side='left', padx=self.PAD_MD)
            cond_type_combo.current(0)
            
            param_frame = ttk.LabelFrame(scrollable_frame, text="触发参数", padding=self.PAD_XS)
            param_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            
            cond_target_var = tk.StringVar(value="f1")
            cond_x_var = tk.StringVar(value="0")
            cond_y_var = tk.StringVar(value="0")
            cond_btn_var = tk.StringVar(value="left")
            cond_dir_var = tk.StringVar(value="向上")
            cond_dur_var = tk.StringVar(value="1")
            
            def build_param_ui():
                for w in param_frame.winfo_children():
                    w.destroy()
                selected_label = cond_type_combo.get()
                ctype = cond_type_map.get(selected_label, "keyboard")
                cond_type_var.set(ctype)
                
                if ctype in ('keyboard', 'press', 'key_hold'):
                    ttk.Label(param_frame, text="触发按键:").pack(anchor='w')
                    key_row = ttk.Frame(param_frame)
                    key_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Entry(key_row, textvariable=cond_target_var, width=15, state='readonly').pack(side='left')
                    ttk.Button(key_row, text="选择按键",
                              command=lambda: cond_target_var.set(self.select_key_dialog("选择触发按键") or cond_target_var.get())).pack(side='left', padx=self.PAD_XS)
                    if ctype == 'key_hold':
                        ttk.Label(param_frame, text="长按时长(秒):").pack(anchor='w', pady=(self.PAD_XS, 0))
                        ttk.Entry(param_frame, textvariable=cond_dur_var, width=10).pack(anchor='w')
                elif ctype in ('click', 'double_click', 'hold'):
                    ttk.Label(param_frame, text="鼠标按钮:").pack(anchor='w')
                    btn_row = ttk.Frame(param_frame)
                    btn_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Combobox(btn_row, values=["left", "right", "middle"],
                                textvariable=cond_btn_var, width=12, state="readonly").pack(side='left')
                    if ctype == 'hold':
                        ttk.Label(param_frame, text="长按时长(秒):").pack(anchor='w', pady=(self.PAD_XS, 0))
                        ttk.Entry(param_frame, textvariable=cond_dur_var, width=10).pack(anchor='w')
                elif ctype in ('right_click', 'left_click'):
                    fixed_btn = "右键" if ctype == 'right_click' else "左键"
                    ttk.Label(param_frame, text=f"固定按钮: {fixed_btn}").pack(anchor='w')
                    cond_btn_var.set('right' if ctype == 'right_click' else 'left')
                elif ctype == 'move':
                    ttk.Label(param_frame, text="目标坐标:").pack(anchor='w')
                    coord_row = ttk.Frame(param_frame)
                    coord_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(coord_row, text="X:").pack(side='left')
                    ttk.Entry(coord_row, textvariable=cond_x_var, width=8).pack(side='left', padx=self.PAD_XS)
                    ttk.Label(coord_row, text="Y:").pack(side='left')
                    ttk.Entry(coord_row, textvariable=cond_y_var, width=8).pack(side='left', padx=self.PAD_XS)
                    ttk.Button(coord_row, text="获取当前位置",
                              command=lambda: (cond_x_var.set(str(self.autoclicker.get_current_position().x)),
                                             cond_y_var.set(str(self.autoclicker.get_current_position().y)))).pack(side='left', padx=self.PAD_XS)
                elif ctype == 'scroll':
                    ttk.Label(param_frame, text="滚动方向:").pack(anchor='w')
                    ttk.Combobox(param_frame, values=["向上", "向下", "向左", "向右"],
                                textvariable=cond_dir_var, width=12, state="readonly").pack(anchor='w', pady=(0, self.PAD_XS))
                elif ctype == 'hotkey':
                    ttk.Label(param_frame, text="快捷键组合(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=25).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: ctrl+c, alt+tab, shift+f1", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'type':
                    ttk.Label(param_frame, text="检测文本(剪贴板包含此文本时触发):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="监听剪贴板变化，匹配到指定文本后触发", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'fill':
                    ttk.Label(param_frame, text="检测到剪贴板为纯数字时触发").pack(anchor='w')
                    ttk.Label(param_frame, text="监听剪贴板变化，检测到纯数字内容后触发", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'open_file_listen':
                    ttk.Label(param_frame, text="监听文件路径:").pack(anchor='w')
                    file_row = ttk.Frame(param_frame)
                    file_row.pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Entry(file_row, textvariable=cond_target_var, width=30).pack(side='left')
                    def browse_file():
                        fp = filedialog.askopenfilename(title="选择监听文件", parent=self.window)
                        if fp:
                            cond_target_var.set(fp)
                    ttk.Button(file_row, text="浏览", command=browse_file).pack(side='left', padx=self.PAD_XS)
                    cond_dir_var.set("exists")
                    ttk.Label(param_frame, text="检测模式:").pack(anchor='w', pady=(self.PAD_XS, 0))
                    ttk.Combobox(param_frame, values=["文件出现(存在)", "文件修改(时间变化)"],
                                 textvariable=cond_dir_var, width=20, state="readonly").pack(anchor='w')
                elif ctype == 'open_url_listen':
                    ttk.Label(param_frame, text="检测URL关键词(剪贴板包含时触发):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: baidu.com, taobao.com", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'browser_open':
                    ttk.Label(param_frame, text="检测浏览器窗口标题包含:").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="检测所有可见窗口标题，包含关键词时触发", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                    ttk.Label(param_frame, text="例: 百度, Baidu, taobao, 淘宝", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'multi_key':
                    ttk.Label(param_frame, text="同时按下的按键(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: ctrl+shift+a", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'multi_mouse':
                    ttk.Label(param_frame, text="鼠标事件组合(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: left+double, right+scroll", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
                elif ctype == 'multi_key_mouse':
                    ttk.Label(param_frame, text="键鼠组合事件(用+连接):").pack(anchor='w')
                    ttk.Entry(param_frame, textvariable=cond_target_var, width=30).pack(fill='x', pady=(0, self.PAD_XS))
                    ttk.Label(param_frame, text="例: ctrl+left_click, shift+double_click", foreground="gray", font=("Microsoft YaHei UI", 8)).pack(anchor='w')
            
            cond_type_combo.bind("<<ComboboxSelected>>", lambda e: build_param_ui())
            build_param_ui()

            multi_frame = ttk.LabelFrame(scrollable_frame, text="触发条件（支持多个）", padding=self.PAD_XS)
            multi_frame.pack(fill='both', expand=True, padx=self.PAD_MD, pady=self.PAD_XS)
            
            tree_container = ttk.Frame(multi_frame)
            tree_container.pack(fill='both', expand=True)
            
            condition_tree = ttk.Treeview(tree_container, columns=('序号', '类型', '按键'), show='headings', height=5)
            condition_tree.heading('序号', text='序号')
            condition_tree.heading('类型', text='类型')
            condition_tree.heading('按键', text='按键')
            
            condition_tree.column('序号', width=50, stretch=False)
            condition_tree.column('类型', width=80, stretch=False)
            condition_tree.column('按键', width=200, stretch=False)
            
            cond_scrollbar_y = ttk.Scrollbar(tree_container, orient="vertical", command=condition_tree.yview)
            condition_tree.configure(yscrollcommand=cond_scrollbar_y.set)
            cond_scrollbar_x = ttk.Scrollbar(tree_container, orient="horizontal", command=condition_tree.xview)
            condition_tree.configure(xscrollcommand=cond_scrollbar_x.set)
            
            condition_tree.grid(row=0, column=0, sticky='nsew')
            cond_scrollbar_y.grid(row=0, column=1, sticky='ns')
            cond_scrollbar_x.grid(row=1, column=0, sticky='ew')
            
            tree_container.grid_rowconfigure(0, weight=1)
            tree_container.grid_columnconfigure(0, weight=1)

            def add_condition():
                ctype = cond_type_var.get()
                
                cond_type_label = cond_type_combo.get()
                
                if ctype in ('keyboard', 'press'):
                    keys = self.select_multi_keys_dialog("选择触发按键")
                    for key in keys:
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, key))
                elif ctype == 'key_hold':
                    key = self.select_key_dialog("选择长按按键")
                    if key:
                        dur = cond_dur_var.get()
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"{key} ({dur}秒)"))
                elif ctype in ('click', 'double_click', 'hold'):
                    btn = cond_btn_var.get()
                    if ctype == 'hold':
                        dur = cond_dur_var.get()
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"{btn} ({dur}秒)"))
                    else:
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, btn))
                elif ctype in ('right_click', 'left_click'):
                    btn = '右键' if ctype == 'right_click' else '左键'
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, btn))
                elif ctype == 'move':
                    x, y = cond_x_var.get(), cond_y_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"({x}, {y})"))
                elif ctype == 'scroll':
                    direction = cond_dir_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, direction))
                elif ctype == 'hotkey':
                    hk = simpledialog.askstring("快捷键", "输入快捷键组合(如 ctrl+c):", parent=self.window)
                    if hk:
                        cond_target_var.set(hk)
                        condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, hk))
                elif ctype == 'type':
                    txt = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, txt))
                elif ctype == 'fill':
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, "纯数字"))
                elif ctype == 'open_file_listen':
                    fp = cond_target_var.get()
                    mode = cond_dir_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, f"{fp} [{mode}]"))
                elif ctype == 'open_url_listen':
                    kw = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, kw))
                elif ctype == 'browser_open':
                    kw = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, kw))
                elif ctype in ('multi_key', 'multi_mouse', 'multi_key_mouse'):
                    combo = cond_target_var.get()
                    condition_tree.insert('', 'end', values=(len(condition_tree.get_children())+1, cond_type_label, combo))
            
            btn_frame1 = ttk.Frame(scrollable_frame)
            btn_frame1.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            ttk.Button(btn_frame1, text="添加条件", command=add_condition).pack(side='left', padx=self.PAD_XS)
            ttk.Button(btn_frame1, text="删除选中", command=lambda: condition_tree.delete(condition_tree.selection()[0] if condition_tree.selection() else None)).pack(side='left', padx=self.PAD_XS)
            ttk.Button(btn_frame1, text="清空列表", command=lambda: [condition_tree.delete(item) for item in condition_tree.get_children()]).pack(side='left', padx=self.PAD_XS)

            sub_frame = ttk.LabelFrame(scrollable_frame, text="触发后执行的子动作", padding=self.PAD_XS)
            sub_frame.pack(fill='both', expand=True, padx=self.PAD_MD, pady=self.PAD_XS)
            
            sub_tree_container = ttk.Frame(sub_frame)
            sub_tree_container.pack(fill='both', expand=True)
            
            sub_tree = ttk.Treeview(sub_tree_container, columns=('序号', '类型', '参数'), show='headings', height=8)
            sub_tree.heading('序号', text='序号')
            sub_tree.heading('类型', text='类型')
            sub_tree.heading('参数', text='参数')
            
            sub_tree.column('序号', width=50, stretch=False)
            sub_tree.column('类型', width=100, stretch=False)
            sub_tree.column('参数', width=300, stretch=False)
            
            sub_scrollbar_y = ttk.Scrollbar(sub_tree_container, orient="vertical", command=sub_tree.yview)
            sub_tree.configure(yscrollcommand=sub_scrollbar_y.set)
            sub_scrollbar_x = ttk.Scrollbar(sub_tree_container, orient="horizontal", command=sub_tree.xview)
            sub_tree.configure(xscrollcommand=sub_scrollbar_x.set)
            
            sub_tree.grid(row=0, column=0, sticky='nsew')
            sub_scrollbar_y.grid(row=0, column=1, sticky='ns')
            sub_scrollbar_x.grid(row=1, column=0, sticky='ew')
            
            sub_tree_container.grid_rowconfigure(0, weight=1)
            sub_tree_container.grid_columnconfigure(0, weight=1)

            action_display_map = self._get_action_display_map()

            sub_actions_data = []

            def add_sub_action_callback(action_type, action_func):
                def add_action_to_tree(action_params):
                    params_str = ', '.join([f"{k}={v}" for k, v in action_params.items()])
                    display_name = action_display_map.get(action_type, action_type)
                    item_id = sub_tree.insert('', 'end', values=(len(sub_tree.get_children())+1, display_name, params_str))
                    sub_actions_data.append({'item_id': item_id, 'type': action_type, 'params': action_params})
                action_func(add_action_to_tree)
            
            btn_frame2 = ttk.LabelFrame(scrollable_frame, text="添加子动作", padding=self.PAD_XS)
            btn_frame2.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            self.create_action_button_frame(btn_frame2, add_sub_action_callback)
            
            edit_btn_frame = ttk.Frame(scrollable_frame)
            edit_btn_frame.pack(fill='x', padx=self.PAD_MD, pady=self.PAD_XS)
            def _delete_selected_sub():
                sel = sub_tree.selection()
                if not sel:
                    return
                item_id = sel[0]
                idx = sub_tree.index(item_id)
                sub_tree.delete(item_id)
                if 0 <= idx < len(sub_actions_data):
                    del sub_actions_data[idx]

            def _clear_sub_list():
                sub_tree.delete(*sub_tree.get_children())
                sub_actions_data.clear()

            ttk.Button(edit_btn_frame, text="删除选中", command=_delete_selected_sub).pack(side='left', padx=self.PAD_XS)
            ttk.Button(edit_btn_frame, text="清空列表", command=_clear_sub_list).pack(side='left', padx=self.PAD_XS)
            
            result = {'confirmed': False, 'params': {}}

            def on_confirm():
                condition_type = cond_type_var.get()
                
                conditions = []
                for item in condition_tree.get_children():
                    values = condition_tree.item(item)['values']
                    conditions.append(values[2])
                
                sub_actions = []
                for data in sub_actions_data:
                    kwargs = {k: v for k, v in data['params'].items() if k != 'type'}
                    sub_actions.append({'type': data['type'], 'kwargs': kwargs})

                if not conditions:
                    messagebox.showerror("错误", "请至少添加一个触发条件", parent=self.window)
                    return
                
                params = {
                    'condition_type': condition_type,
                    'target_keys': conditions,
                    'sub_actions': sub_actions
                }
                
                if condition_type == 'move' and conditions:
                    try:
                        coord_str = conditions[0].strip("()")
                        x, y = coord_str.split(",")
                        params['target_x'] = int(x.strip())
                        params['target_y'] = int(y.strip())
                    except:
                        pass
                elif condition_type in ('hold', 'key_hold'):
                    params['duration'] = float(cond_dur_var.get() or 1)
                elif condition_type == 'type':
                    params['target_key'] = cond_target_var.get()
                elif condition_type == 'fill':
                    pass
                elif condition_type == 'open_file_listen':
                    params['target_key'] = cond_target_var.get()
                    mode_map = {"文件出现(存在)": "exists", "文件修改(时间变化)": "modified"}
                    params['monitor_mode'] = mode_map.get(cond_dir_var.get(), "exists")
                elif condition_type == 'open_url_listen':
                    params['target_key'] = cond_target_var.get()
                elif condition_type == 'browser_open':
                    params['target_key'] = cond_target_var.get()
                elif condition_type in ('multi_key', 'multi_mouse', 'multi_key_mouse'):
                    params['target_key'] = cond_target_var.get()
                
                result['confirmed'] = True
                result['params'] = params
                dialog.destroy()

            def on_cancel():
                dialog.destroy()

            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.pack(pady=self.PAD_MD)

            ttk.Button(btn_frame, text="确定", command=on_confirm, width=12).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel, width=12).pack(side='left', padx=self.PAD_MD)

            self.window.wait_window(dialog)

            if result['confirmed']:
                params = result['params']
                self._add_or_insert_action(insert_index, 'conditional', **params)
                self.update_action_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加条件控制动作时出错: {e}", parent=self.window)

    def add_fill_action(self, insert_index=None):
        try:
            dialog, dialog_width, dialog_height = self.create_adaptive_dialog("填充数字设置", 0.5, 0.5)

            canvas = tk.Canvas(dialog, borderwidth=0, background=self.COLOR_CARD)
            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")

            dialog.grid_rowconfigure(0, weight=1)
            dialog.grid_columnconfigure(0, weight=1)

            ttk.Label(scrollable_frame, text="总位数:").grid(row=0, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            total_var = tk.StringVar(value="4")
            total_spin = ttk.Spinbox(scrollable_frame, from_=1, to=10, textvariable=total_var, width=10)
            total_spin.grid(row=0, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="起始数字:").grid(row=1, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            start_var = tk.StringVar(value="0")
            start_entry = ttk.Entry(scrollable_frame, textvariable=start_var, width=12)
            start_entry.grid(row=1, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="结束数字:").grid(row=2, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            end_var = tk.StringVar(value="9999")
            end_entry = ttk.Entry(scrollable_frame, textvariable=end_var, width=12)
            end_entry.grid(row=2, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="前缀(固定):").grid(row=3, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            prefix_var = tk.StringVar(value="")
            prefix_entry = ttk.Entry(scrollable_frame, textvariable=prefix_var, width=12)
            prefix_entry.grid(row=3, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="后缀(固定):").grid(row=4, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            suffix_var = tk.StringVar(value="")
            suffix_entry = ttk.Entry(scrollable_frame, textvariable=suffix_var, width=12)
            suffix_entry.grid(row=4, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            ttk.Label(scrollable_frame, text="输入间隔(秒):").grid(row=5, column=0, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)
            interval_var = tk.StringVar(value="0.5")
            interval_spin = ttk.Spinbox(scrollable_frame, from_=0, to=10, increment=0.1, textvariable=interval_var, width=10)
            interval_spin.grid(row=5, column=1, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            progress_info_frame = ttk.LabelFrame(scrollable_frame, text="当前进度", padding=self.PAD_XS)
            progress_info_frame.grid(row=6, column=0, columnspan=2, sticky='ew', padx=self.PAD_MD, pady=self.PAD_XS)

            last_progress_label = ttk.Label(progress_info_frame, text="", foreground=self.COLOR_ACCENT, font=self.FONT_NORMAL)
            last_progress_label.pack(anchor='w')

            progress_file = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AutoClicker', 'fill_progress.json')
            os.makedirs(os.path.dirname(progress_file), exist_ok=True)
            last_progress = self._load_fill_progress(progress_file)

            if last_progress:
                last_progress_label.config(text=f"上次结束于: {last_progress.get('display', '未知')}")
            else:
                last_progress_label.config(text="无保存的进度（从头开始）")

            def reset_progress():
                if os.path.exists(progress_file):
                    os.remove(progress_file)
                    last_progress_label.config(text="进度已重置（将从头开始）")
                    start_var.set("0")
                    update_example()
                else:
                    messagebox.showinfo("提示", "没有需要重置的进度", parent=self.window)

            reset_btn = ttk.Button(progress_info_frame, text="重置进度", command=reset_progress)
            reset_btn.pack(anchor='w', pady=self.PAD_XS)

            example_frame = ttk.LabelFrame(scrollable_frame, text="示例预览", padding=self.PAD_MD)
            example_frame.grid(row=7, column=0, columnspan=2, sticky='ew', padx=self.PAD_MD, pady=self.PAD_XS)

            example_label = ttk.Label(example_frame, text="", foreground=self.COLOR_PRIMARY, font=self.FONT_HEADING)
            example_label.pack(anchor='w')

            def update_example(*args):
                try:
                    total = int(total_var.get())
                    start = int(start_var.get())
                    end = int(end_var.get())
                    prefix = prefix_var.get()
                    suffix = suffix_var.get()

                    fixed_len = len(prefix) + len(suffix)
                    if fixed_len >= total:
                        example_label.config(text="错误: 前缀+后缀长度不能大于总位数")
                        return

                    fill_digits = total - fixed_len
                    if fill_digits <= 0:
                        example_label.config(text="错误: 填充位数必须大于0")
                        return

                    max_val = 10 ** fill_digits - 1
                    if start > max_val:
                        start = 0
                        start_var.set("0")
                    if end > max_val:
                        end = max_val
                        end_var.set(str(max_val))
                    if start > end:
                        start, end = end, start
                        start_var.set(str(start))
                        end_var.set(str(end))

                    first_num = str(start).zfill(fill_digits)
                    last_num = str(end).zfill(fill_digits)
                    first_full = prefix + first_num + suffix
                    last_full = prefix + last_num + suffix

                    count = end - start + 1
                    example_label.config(text=f"格式: {first_full} ~ {last_full}\n每次填1个数字，总计 {count} 个\n请在\"重复次数\"中设置为 {count}")
                except ValueError:
                    example_label.config(text="请输入有效的数字")

            total_var.trace('w', update_example)
            start_var.trace('w', update_example)
            end_var.trace('w', update_example)
            prefix_var.trace('w', update_example)
            suffix_var.trace('w', update_example)

            update_example()

            help_text = ttk.Label(scrollable_frame, text="说明: 每次运行脚本只填入一个数字\n前缀/后缀为固定部分，范围用于设置起止数字\n总填充次数 = 重复次数（设置10000次即可填满0000-9999）",
                                foreground=self.COLOR_TEXT_SECONDARY, font=self.FONT_SMALL)
            help_text.grid(row=9, column=0, columnspan=2, sticky='w', padx=self.PAD_MD, pady=self.PAD_XS)

            result = {'confirmed': False, 'params': {}}

            def on_confirm():
                try:
                    total = int(total_var.get())
                    start = int(start_var.get())
                    end = int(end_var.get())
                    prefix = prefix_var.get()
                    suffix = suffix_var.get()
                    interval = float(interval_var.get())

                    fixed_len = len(prefix) + len(suffix)
                    if fixed_len >= total:
                        messagebox.showerror("错误", "前缀+后缀长度不能大于等于总位数", parent=self.window)
                        return
                    if len(prefix) + len(suffix) + len(str(start)) > total or len(prefix) + len(suffix) + len(str(end)) > total:
                        messagebox.showerror("错误", "起始或结束数字超出了可表示的范围", parent=self.window)
                        return

                    result['confirmed'] = True
                    result['params'] = {
                        'total_digits': total,
                        'start': start,
                        'end': end,
                        'prefix': prefix,
                        'suffix': suffix,
                        'interval': interval
                    }
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showerror("错误", f"请输入有效的数字: {e}", parent=self.window)

            def on_cancel():
                dialog.destroy()

            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.grid(row=10, column=0, columnspan=2, pady=self.PAD_MD, sticky='ew')

            ttk.Button(btn_frame, text="确定", command=on_confirm).pack(side='left', padx=self.PAD_MD)
            ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='left', padx=self.PAD_MD)

            self.window.wait_window(dialog)

            if result['confirmed']:
                params = result['params']
                action_params = {k: v for k, v in params.items() if k != 'save_progress'}
                action = self._add_or_insert_action(insert_index, 'fill', **action_params)
                self.update_action_list()

                fill_digits = params['total_digits'] - len(params['prefix']) - len(params['suffix'])
                prefix_display = f"前缀'{params['prefix']}'" if params['prefix'] else "无前缀"
                suffix_display = f"后缀'{params['suffix']}'" if params['suffix'] else "无后缀"
                count = params['end'] - params['start'] + 1

        except Exception as e:
            messagebox.showerror("错误", f"添加填充数字动作时出错: {e}", parent=self.window)

    def _load_fill_progress(self, filepath):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载填充进度失败: {e}")
        return None

    def _save_fill_progress(self, filepath, data):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"填充进度已保存: {data.get('display', '未知')}")
        except Exception as e:
            print(f"保存填充进度失败: {e}")

    def _save_fill_progress_from_result(self, result):
        try:
            total_digits = result.get('total_digits')
            end = result.get('end')
            prefix = result.get('prefix', '')
            suffix = result.get('suffix', '')
            next_value = result.get('next_value', 0)
            current_input = result.get('current_input', 0)
            fill_digits = result.get('fill_digits', 0)

            progress_data = {
                'total_digits': total_digits,
                'end': end,
                'prefix': prefix,
                'suffix': suffix,
                'next_value': next_value,
                'fill_digits': fill_digits,
                'display': f"{prefix}{str(current_input).zfill(fill_digits)}{suffix}"
            }

            progress_file = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AutoClicker', 'fill_progress.json')
            os.makedirs(os.path.dirname(progress_file), exist_ok=True)
            self._save_fill_progress(progress_file, progress_data)
            print(f"进度已保存: 下次将填入 {progress_data['display']}")
        except Exception as e:
            print(f"自动保存填充进度失败: {e}")

    def delete_selected_action(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要删除的动作", parent=self.window)
            return
        
        indices = []
        for item in selected:
            index = int(self.tree.item(item)['values'][0]) - 1
            if 0 <= index < len(self.autoclicker.actions):
                indices.append(index)
        for index in sorted(set(indices), reverse=True):
            self._push_history(f"删除动作: {self.autoclicker.actions[index].get('type', 'unknown')}")
            del self.autoclicker.actions[index]
        
        self.update_action_list()
    
    def toggle_action_enabled(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        item_values = self.tree.item(selected_item[0])['values']
        index = int(item_values[0]) - 1
        self._push_history("切换启用状态")
        
        if 0 <= index < len(self.autoclicker.actions):
            action = self.autoclicker.actions[index]
            current = action.get('enabled', True)
            action['enabled'] = not current
            self.update_action_list()
            children = self.tree.get_children()
            if children and index < len(children):
                self.tree.selection_set(children[index])
    
    def _log(self, message):
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"
        
        def _update():
            self.log_text.configure(state='normal')
            self.log_text.insert('end', log_line)
            if self.log_text.index('end-1c').split('.')[0] > '100':
                self.log_text.delete('1.0', 'end-100l')
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
        
        self.window.after(0, _update)
    
    def _clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')
    
    def clear_action_list(self):
        if messagebox.askyesno("确认", "确定要清空所有动作吗？"):
            self._push_history("清空列表")
            self.autoclicker.clear_actions()
            self.update_action_list()
    
    def duplicate_action(self):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0])['values']
        index = int(values[0]) - 1
        if 0 <= index < len(self.autoclicker.actions):
            self._push_history("复制动作")
            new_action = copy.deepcopy(self.autoclicker.actions[index])
            new_action['timestamp'] = time.time()
            self.autoclicker.actions.insert(index + 1, new_action)
            self.update_action_list()
    
    def move_action(self, direction):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0])['values']
        index = int(values[0]) - 1
        new_index = index + direction
        if 0 <= new_index < len(self.autoclicker.actions):
            self._push_history(f"移动动作")
            self.autoclicker.actions[index], self.autoclicker.actions[new_index] = \
                self.autoclicker.actions[new_index], self.autoclicker.actions[index]
            self.update_action_list()
            children = self.tree.get_children()
            if new_index < len(children):
                self.tree.selection_set(children[new_index])
    
    def move_action_to(self, position):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0])['values']
        index = int(values[0]) - 1
        if 0 <= index < len(self.autoclicker.actions):
            self._push_history(f"移动动作到{position}")
            action = self.autoclicker.actions.pop(index)
            if position == 'top':
                self.autoclicker.actions.insert(0, action)
            else:
                self.autoclicker.actions.append(action)
            self.update_action_list()
    
    def select_all_actions(self):
        for item in self.tree.get_children():
            self.tree.selection_add(item)
    
    def deselect_all_actions(self):
        self.tree.selection_remove(*self.tree.selection())
    
    def enable_all_actions(self):
        self._push_history("全部启用")
        for action in self.autoclicker.actions:
            action['enabled'] = True
        self.update_action_list()
    
    def disable_all_actions(self):
        self._push_history("全部禁用")
        for action in self.autoclicker.actions:
            action['enabled'] = False
        self.update_action_list()
    
    def _on_tree_press(self, event):
        self._drag_data['item'] = self.tree.identify_row(event.y)
        self._drag_data['y_start'] = event.y
        self._drag_data['moved'] = False
    
    def _on_tree_drag(self, event):
        if self._drag_data['item']:
            if abs(event.y - self._drag_data['y_start']) > 5:
                self._drag_data['moved'] = True
    
    def _on_tree_release(self, event):
        item = self._drag_data['item']
        target = self.tree.identify_row(event.y)
        
        if item and target and item != target and self._drag_data['moved']:
            children = self.tree.get_children()
            from_idx = children.index(item)
            to_idx = children.index(target)
            
            if 0 <= from_idx < len(self.autoclicker.actions) and 0 <= to_idx < len(self.autoclicker.actions):
                self._push_history("拖拽排序")
                action = self.autoclicker.actions.pop(from_idx)
                self.autoclicker.actions.insert(to_idx, action)
                self.update_action_list()
                new_children = self.tree.get_children()
                if to_idx < len(new_children):
                    self.tree.selection_set(new_children[to_idx])
        
        self._drag_data['item'] = None
        self._drag_data['moved'] = False
    
    def update_action_list(self):
        actions = self.autoclicker.actions
        children = self.tree.get_children()
        need_rebuild = len(children) != len(actions)
        if not need_rebuild:
            for i, action in enumerate(actions):
                kwargs = action['kwargs']
                params_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
                timestamp = time.strftime('%H:%M:%S', time.localtime(action['timestamp']))
                enabled = action.get('enabled', True)
                status = "✓" if enabled else "✗"
                cur = self.tree.item(children[i], 'values')
                if list(cur) != [i + 1, status, action['type'], params_str, timestamp]:
                    need_rebuild = True
                    break
        if need_rebuild:
            for item in children:
                self.tree.delete(item)
            for i, action in enumerate(actions):
                action_type = action['type']
                kwargs = action['kwargs']
                params_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
                timestamp = time.strftime('%H:%M:%S', time.localtime(action['timestamp']))
                enabled = action.get('enabled', True)
                status = "✓" if enabled else "✗"
                item_id = self.tree.insert('', 'end', values=(i+1, status, action_type, params_str, timestamp))
                if not enabled:
                    self.tree.item(item_id, tags=('disabled',))
        
        self.tree.tag_configure('disabled', foreground='gray')
        self.tree.tag_configure('highlight', background='#e3f2fd')

        self._update_status_bar_count()

    
    def start_sequence(self):
        try:
            repeat = int(self.repeat_var.get())
            interval = float(self.interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "请检查重复次数和间隔时间的数值", parent=self.window)
            return

        if self.infinite_loop_var.get():
            repeat = None

        self.pause_btn.config(text="暂停")
        self.autoclicker.running = True
        self.autoclicker.stop_event.clear()
        self.autoclicker.paused_event.clear()
        self._exec_start_time = time.time()
        self._exec_elapsed = 0

        def run_in_thread():
            self._clear_log()
            self._log("=== 开始执行 ===")
            self.autoclicker.run_actions(repeat=repeat, interval=interval)
            self._log("=== 执行结束 ===")

        thread = threading.Thread(target=run_in_thread)
        thread.daemon = True
        self._exec_thread = thread
        thread.start()
    
    def stop_sequence(self):
        self._log("用户停止执行")
        self.autoclicker.stop()
        if self._exec_start_time:
            self._exec_elapsed = time.time() - self._exec_start_time
            self._exec_start_time = None
        self.window.after(0, lambda: messagebox.showinfo("停止", "已停止执行", parent=self.window))
    
    def toggle_pause(self):
        if not self.autoclicker.running:
            return
        if self.autoclicker.paused_event.is_set():
            self.autoclicker.paused_event.clear()
            self.pause_btn.config(text="暂停")
            self._log("继续执行")
        else:
            self.autoclicker.paused_event.set()
            self.pause_btn.config(text="继续")
            self._log("已暂停")
    
    
    def toggle_sequence(self):
        if self.autoclicker.running:
            self.stop_sequence()
        else:
            self.start_sequence()
    
    def save_sequence(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.save_actions(filename):
                pass
            else:
                messagebox.showerror("错误", "保存失败", parent=self.window)
    
    def load_sequence(self):
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.load_actions(filename):
                self._push_history("加载序列")
                self.update_action_list()
                self._add_recent_script(filename)
                pass
            else:
                messagebox.showerror("错误", "加载失败", parent=self.window)
    
    def save_script_txt(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.save_as_txt(filename):
                pass
            else:
                messagebox.showerror("错误", "保存文本文件失败", parent=self.window)
    
    def load_script_txt(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.load_from_txt(filename):
                self.update_action_list()
                self._add_recent_script(filename)
                pass
            else:
                messagebox.showerror("错误", "加载文本文件失败", parent=self.window)
    
    def _load_recent_scripts(self):
        try:
            if os.path.exists(self.recent_config_file):
                with open(self.recent_config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.recent_scripts = [x for x in data if isinstance(x, str)]
        except Exception as e:
            print(f"加载最近打开记录失败: {e}")

    def _save_recent_scripts(self):
        try:
            with open(self.recent_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.recent_scripts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存最近打开记录失败: {e}")

    def _add_recent_script(self, filename):
        filename = os.path.abspath(filename)
        if filename in self.recent_scripts:
            self.recent_scripts.remove(filename)
        self.recent_scripts.insert(0, filename)
        del self.recent_scripts[self.recent_max:]
        self._save_recent_scripts()

    def _remove_recent_script(self, filename):
        if filename in self.recent_scripts:
            self.recent_scripts.remove(filename)
            self._save_recent_scripts()

    def _clear_recent_scripts(self):
        self.recent_scripts.clear()
        self._save_recent_scripts()

    def _load_recent_file(self, filename):
        if not os.path.exists(filename):
            messagebox.showwarning(
                "文件不存在",
                f"文件不存在或已被移动:\n{filename}\n已从最近记录中移除。",
                parent=self.window)
            self._remove_recent_script(filename)
            return
        try:
            ext = os.path.splitext(filename)[1].lower()
            if ext == '.json':
                ok = self.autoclicker.load_actions(filename)
            elif ext == '.txt':
                ok = self.autoclicker.load_from_txt(filename)
            else:
                ok = self.autoclicker.load_actions(filename)
                if not ok:
                    ok = self.autoclicker.load_from_txt(filename)
            if ok:
                self._push_history("加载最近脚本")
                self.update_action_list()
                self._add_recent_script(filename)
            else:
                messagebox.showerror("错误", "加载失败，请确认文件内容有效", parent=self.window)
        except Exception as e:
            messagebox.showerror("错误", f"加载失败: {e}", parent=self.window)

    def _show_recent_menu(self, anchor_widget):
        menu = tk.Menu(self.window, tearoff=0)
        self._recent_menu = menu
        if not self.recent_scripts:
            menu.add_command(label="暂无最近打开的脚本", state='disabled')
            menu.add_separator()
            menu.add_command(label="加载脚本(.json)", command=self.load_sequence)
            menu.add_command(label="加载脚本(.txt)", command=self.load_script_txt)
        else:
            last_path = self.recent_scripts[0]
            menu.add_command(
                label="打开上次脚本: " + os.path.basename(last_path),
                command=lambda p=last_path: self._load_recent_file(p))
            menu.add_separator()
            for idx, path in enumerate(self.recent_scripts[1:]):
                menu.add_command(
                    label=f"[{idx+1}] {os.path.basename(path)}",
                    command=lambda p=path: self._load_recent_file(p))
            menu.add_separator()
            menu.add_command(label="清空最近记录", command=self._clear_recent_scripts)
        try:
            menu.tk_popup(anchor_widget.winfo_rootx(),
                          anchor_widget.winfo_rooty() + anchor_widget.winfo_height())
        finally:
            menu.grab_release()
    

    def _build_launcher_full_code(self, data_json):
        return '''"""自动化脚本 - 独立可执行版"""
import sys
import os
import json
import time
import threading
import re
import random
import math
import tkinter as tk
from tkinter import ttk

# 内嵌脚本数据（以占位符形式内嵌，转义所有引号，避免破坏外层三引号字符串）
SCRIPT_DATA = __SCRIPT_DATA__

# 兼容：SCRIPT_DATA 以 JSON 字符串内嵌时先反序列化为真实动作列表，
# 否则 execute_actions 会逐字符遍历字符串，触发 "'str' object has no attribute 'get'"
if isinstance(SCRIPT_DATA, str):
    try:
        SCRIPT_DATA = json.loads(SCRIPT_DATA)
    except Exception as _e:
        print(f"脚本数据解析失败: {_e}")
        SCRIPT_DATA = []

# ---- 全局共享状态 ----
stop_event = threading.Event()
paused = threading.Event()
status_msg = {"state": "就绪", "loop": 0, "action": "", "total_loops": 1}
_ui_update = None

# ---- 快捷键自定义（本次会话生效）与退格返回上一级状态 ----
hotkey_pause = "f1"
hotkey_stop = "f2"
hotkey_back = "backspace"
back_event = threading.Event()

def _safe_eval_template(expr, ctx):
    """AST 白名单求值模板表达式：仅允许变量/常量/算术比较与白名单函数，禁止对象内省。"""
    import ast as _ast
    allowed_funcs = {'random': random, 'math': math, 'abs': abs, 'min': min, 'max': max,
                     'int': int, 'float': float, 'str': str}
    allowed_attr_bases = {'random', 'math'}

    def _check(node):
        if isinstance(node, _ast.Expression):
            _check(node.body)
        elif isinstance(node, _ast.Name):
            if node.id not in ctx and node.id not in allowed_funcs:
                raise ValueError("不允许的变量: %s" % node.id)
        elif isinstance(node, _ast.Attribute):
            if not (isinstance(node.value, _ast.Name) and node.value.id in allowed_attr_bases):
                raise ValueError("不允许的属性访问: %s" % node.attr)
            _check(node.value)
        elif isinstance(node, _ast.Constant):
            return
        elif isinstance(node, _ast.Call):
            _check(node.func)
            for a in node.args:
                _check(a)
            for kw in node.keywords:
                _check(kw.value)
        elif isinstance(node, (_ast.BinOp, _ast.UnaryOp, _ast.Compare, _ast.BoolOp)):
            for child in _ast.iter_child_nodes(node):
                _check(child)
        elif isinstance(node, (_ast.operator, _ast.cmpop, _ast.boolop, _ast.unaryop, _ast.Load, _ast.keyword)):
            return
        else:
            raise ValueError("不允许的表达式节点: %s" % type(node).__name__)

    tree = _ast.parse(expr, mode='eval')
    _check(tree)
    return eval(compile(tree, '<template>', 'eval'), {"__builtins__": {}}, dict(ctx, **allowed_funcs))

def _select_key_dialog(parent, title="选择按键"):
    """按键选择对话框（launcher 侧实现，参考主程序 select_key_dialog 的分类标签页方式）。
    返回键名字符串（小写，如 'f1' / 'backspace' / 'a'），取消返回 None。
    """
    result = {'key': None}
    win = tk.Toplevel(parent)
    win.title(title)
    win.attributes('-topmost', True)
    win.resizable(False, False)
    win.minsize(430, 280)

    categories = {
        "字母": [chr(i) for i in range(ord('a'), ord('z') + 1)],
        "数字": [str(i) for i in range(0, 10)],
        "功能键": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
        "控制键": ["space", "enter", "tab", "esc", "backspace", "delete", "shift", "ctrl", "alt", "caps_lock", "cmd"],
        "导航键": ["home", "end", "page_up", "page_down", "insert", "menu", "up", "down", "left", "right"],
        "其他": ["print_screen", "scroll_lock", "pause", "num_lock"],
    }

    nb = ttk.Notebook(win)
    nb.pack(fill='both', expand=True, padx=8, pady=8)

    def choose(k):
        result['key'] = k.lower()
        win.destroy()

    for cat, keys in categories.items():
        f = ttk.Frame(nb)
        nb.add(f, text=cat)
        cols = 10
        for i, k in enumerate(keys):
            r = i // cols
            c = i % cols
            ttk.Button(f, text=k, width=8,
                       command=lambda kk=k: choose(kk)).grid(row=r, column=c, padx=2, pady=2, sticky='ew')
            f.grid_columnconfigure(c, weight=1)
        for rr in range((len(keys) + cols - 1) // cols):
            f.grid_rowconfigure(rr, weight=1)

    ttk.Button(win, text="取消", command=win.destroy).pack(pady=(0, 8))

    if parent.winfo_exists():
        parent.wait_window(win)
    return result['key']


def _custom_hotkey_dialog(parent, hk_pause, hk_stop, hk_back):
    """快捷键自定义对话框：修改三个 StringVar（暂停/继续、停止、返回上一级）的值。"""
    win = tk.Toplevel(parent)
    win.title("自定义快捷键")
    win.attributes('-topmost', True)
    win.resizable(False, False)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text="自定义本会话快捷键（默认: F1=暂停/继续, F2=停止, Backspace=返回上一级）",
              foreground="gray", wraplength=360, justify='left').pack(anchor='w', pady=(0, 8))

    def make_pick(var):
        def _p():
            k = _select_key_dialog(win, "选择按键")
            if k:
                var.set(k)
        return _p

    def row(text, var):
        r = ttk.Frame(frame)
        r.pack(fill='x', pady=3)
        ttk.Label(r, text=text, width=12).pack(side='left')
        ttk.Entry(r, textvariable=var, width=12, state='readonly').pack(side='left', padx=6)
        ttk.Button(r, text="选择...", command=make_pick(var)).pack(side='left')

    row("暂停/继续:", hk_pause)
    row("停止:", hk_stop)
    row("返回上一级:", hk_back)

    ttk.Button(frame, text="确定", command=win.destroy).pack(pady=(10, 0))

    if parent.winfo_exists():
        parent.wait_window(win)


def show_config_dialog():
    """显示初始配置对话框"""
    dialog = tk.Tk()
    dialog.title("自动化脚本执行")
    dialog.resizable(True, True)
    dialog.minsize(380, 260)
    dialog.attributes('-topmost', True)
    
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - 190
    y = (dialog.winfo_screenheight() // 2) - 130
    dialog.geometry(f'+{x}+{y}')
    
    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill='both', expand=True)
    
    ttk.Label(main_frame, text="自动化脚本执行", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 8))
    ttk.Label(main_frame, text=f"共 {len(SCRIPT_DATA)} 个动作待执行").pack(anchor='w', pady=(0, 8))
    
    count_frame = ttk.Frame(main_frame)
    count_frame.pack(fill='x', pady=3)
    ttk.Label(count_frame, text="执行次数:").pack(side='left')
    count_var = tk.StringVar(value="1")
    ttk.Spinbox(count_frame, from_=-1, to=9999, textvariable=count_var, width=8).pack(side='left', padx=10)
    ttk.Label(count_frame, text="(-1为无限循环)").pack(side='left')
    
    interval_frame = ttk.Frame(main_frame)
    interval_frame.pack(fill='x', pady=3)
    ttk.Label(interval_frame, text="循环间隔(秒):").pack(side='left')
    interval_var = tk.StringVar(value="0.5")
    ttk.Spinbox(interval_frame, from_=0, to=60, increment=0.1, textvariable=interval_var, width=8).pack(side='left', padx=10)
    
    # 快捷键自定义（本会话生效）
    hk_pause = tk.StringVar(value="f1")
    hk_stop = tk.StringVar(value="f2")
    hk_back = tk.StringVar(value="backspace")

    def open_hotkey_custom():
        _custom_hotkey_dialog(dialog, hk_pause, hk_stop, hk_back)

    ttk.Label(main_frame, text=f"快捷键: {hotkey_pause} = 暂停/继续 | {hotkey_stop} = 停止 | {hotkey_back} = 返回上一级",
             foreground="gray", font=("Microsoft YaHei UI", 9)).pack(anchor='w', pady=(10, 5))
    
    result = {'count': 1, 'interval': 0.5, 'confirmed': False}
    
    def on_start():
        global hotkey_pause, hotkey_stop, hotkey_back
        try:
            result['count'] = int(count_var.get())
            result['interval'] = float(interval_var.get())
        except ValueError:
            pass
        hotkey_pause = hk_pause.get().strip().lower() or "f1"
        hotkey_stop = hk_stop.get().strip().lower() or "f2"
        hotkey_back = hk_back.get().strip().lower() or "backspace"
        result['confirmed'] = True
        dialog.destroy()
    
    def on_cancel():
        result['confirmed'] = False
        dialog.destroy()
    
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=(10, 0))
    ttk.Button(btn_frame, text="开始执行", command=on_start).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="自定义快捷键", command=open_hotkey_custom).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side='right', padx=5)
    
    dialog.mainloop()
    return result

def show_control_panel():
    """显示常驻控制面板"""
    global _ui_update
    
    root = tk.Tk()
    root.title("自动化脚本控制面板")
    root.resizable(True, True)
    root.minsize(360, 240)
    root.attributes('-topmost', True)
    
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 180
    y = (root.winfo_screenheight() // 2) - 120
    root.geometry(f'+{x}+{y}')
    
    main = ttk.Frame(root, padding=15)
    main.pack(fill='both', expand=True)
    
    # 状态标签
    ttk.Label(main, text="控制面板", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor='w', pady=(0, 10))
    
    state_label = ttk.Label(main, text="状态: 就绪", font=("Microsoft YaHei UI", 10))
    state_label.pack(anchor='w', pady=2)
    
    loop_label = ttk.Label(main, text="循环: 0 / 1", font=("Microsoft YaHei UI", 10))
    loop_label.pack(anchor='w', pady=2)
    
    action_label = ttk.Label(main, text="当前动作: 无", font=("Microsoft YaHei UI", 9), foreground="gray")
    action_label.pack(anchor='w', pady=2)
    
    # 进度条
    progress_var = tk.DoubleVar(value=0)
    progress_bar = ttk.Progressbar(main, variable=progress_var, maximum=len(SCRIPT_DATA), length=320)
    progress_bar.pack(fill='x', pady=(10, 5))
    
    # 按钮
    btn_frame = ttk.Frame(main)
    btn_frame.pack(fill='x', pady=(10, 0))
    
    pause_btn = ttk.Button(btn_frame, text="暂停")
    pause_btn.pack(side='left', padx=5)
    
    stop_btn = ttk.Button(btn_frame, text="停止", command=lambda: stop_event.set())
    stop_btn.pack(side='left', padx=5)
    
    def toggle_pause():
        if paused.is_set():
            paused.clear()
            pause_btn.config(text="暂停")
            state_label.config(text="状态: 运行中", foreground="green")
            status_msg["state"] = "运行中"
        else:
            paused.set()
            pause_btn.config(text="继续")
            state_label.config(text="状态: 已暂停", foreground="orange")
            status_msg["state"] = "已暂停"
    
    pause_btn.config(command=toggle_pause)
    
    def on_stop():
        stop_event.set()
        if paused.is_set():
            paused.clear()
        state_label.config(text="状态: 已停止", foreground="red")
        pause_btn.config(state='disabled')
        status_msg["state"] = "已停止"
    
    stop_btn.config(command=on_stop)
    
    def ui_update():
        if not root.winfo_exists():
            return
        state_label.config(text=f"状态: {status_msg['state']}")
        if status_msg['state'] == "运行中":
            state_label.config(foreground="green")
        elif status_msg['state'] == "已暂停":
            state_label.config(foreground="orange")
        elif status_msg['state'] == "已停止":
            state_label.config(foreground="red")
        
        loop_label.config(text=f"循环: {status_msg['loop']} / {status_msg['total_loops']}")
        action_label.config(text=f"当前动作: {status_msg['action']}")
        
        # 更新进度条
        total = len(SCRIPT_DATA)
        if total > 0:
            progress_var.set(status_msg.get('action_idx', 0))
        
        # 检测退格返回上一级：由 UI 主线程主动关闭控制面板
        if back_event.is_set():
            root.destroy()
            return
        
        root.after(100, ui_update)
    
    _ui_update = ui_update
    ui_update()
    
    return root

def run_script():
    """运行嵌入的自动化脚本"""
    import pyautogui
    
    PYNPUT_AVAILABLE = False
    try:
        from pynput import mouse, keyboard
        from pynput.keyboard import Key, Listener as KeyboardListener
        PYNPUT_AVAILABLE = True
    except ImportError:
        pass

    # OCR 可选依赖（与主程序一致：未安装时打印提示并跳过，不影响其他动作）
    OCR_AVAILABLE = False
    OCR_BACKEND = None
    try:
        from rapidocr_onnxruntime import RapidOCR
        OCR_BACKEND = 'rapidocr_onnxruntime'
        OCR_AVAILABLE = True
    except ImportError:
        try:
            from rapidocr import RapidOCR
            OCR_BACKEND = 'rapidocr'
            OCR_AVAILABLE = True
        except ImportError:
            try:
                import pytesseract
                # 显式配置 Tesseract 可执行路径与语言数据目录（先探测，探测失败保持默认走 PATH）
                if os.path.exists(r'E:\Tesseract-OCR\tesseract.exe'):
                    pytesseract.pytesseract.tesseract_cmd = r'E:\Tesseract-OCR\tesseract.exe'
                if os.path.exists(r'E:\Tesseract-OCR\tessdata'):
                    os.environ['TESSDATA_PREFIX'] = r'E:\Tesseract-OCR\tessdata'
                OCR_BACKEND = 'pytesseract'
                OCR_AVAILABLE = True
            except ImportError:
                OCR_AVAILABLE = False
                OCR_BACKEND = None
    _ocr_engine_cache = {'obj': None}

    def _get_ocr_engine():
        """获取/缓存 OCR 引擎实例（RapidOCR 首次加载较慢，缓存后复用）"""
        if _ocr_engine_cache['obj'] is None and OCR_AVAILABLE:
            try:
                if OCR_BACKEND in ('rapidocr', 'rapidocr_onnxruntime'):
                    from rapidocr_onnxruntime import RapidOCR
                    _ocr_engine_cache['obj'] = RapidOCR()
                elif OCR_BACKEND == 'pytesseract':
                    _ocr_engine_cache['obj'] = 'pytesseract'
            except Exception:
                _ocr_engine_cache['obj'] = None
        return _ocr_engine_cache['obj']

    def _ocr_read(region=None, min_score=0.5, scale=1.0):
        """屏幕文字 OCR 识别与定位（launcher 独立实现，与主程序 ocr_read 对齐）：
        截屏 → 灰度/缩放 → 识别 → 阅读顺序排序 → 返回 {text,x,y,w,h,cx,cy,score} 列表
        """
        if not OCR_AVAILABLE:
            print("未安装 OCR 依赖，请运行 pip install rapidocr_onnxruntime 后重试")
            return None
        # 解析识别区域：空 = 全屏；'x,y,w,h' 字符串 → (x, y, w, h)
        region_tuple = None
        if region:
            try:
                parts = [float(p.strip()) for p in str(region).split(',')]
                if len(parts) == 4:
                    region_tuple = tuple(int(p) for p in parts)
                else:
                    print(f"OCR 区域格式错误（应为 x,y,w,h）: {region}，将按全屏识别")
            except Exception as e:
                print(f"OCR 区域解析失败: {e}，将按全屏识别")
        try:
            if region_tuple:
                img = pyautogui.screenshot(region=region_tuple)
            else:
                img = pyautogui.screenshot()
        except Exception as e:
            print(f"OCR 截屏失败: {e}")
            return None
        # 性能优化：转灰度 + 可选缩放（缩放后坐标按比例还原为屏幕真实坐标）
        try:
            scale = float(scale)
            if scale <= 0:
                scale = 1.0
        except (TypeError, ValueError):
            scale = 1.0
        sx = 1.0 / scale if scale else 1.0
        try:
            if scale != 1.0:
                from PIL import Image
                new_w = max(1, int(img.width * scale))
                new_h = max(1, int(img.height * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)
            img = img.convert('L')
            try:
                import numpy as np
                img = np.array(img)
            except Exception:
                pass
        except Exception:
            pass
        raw_results = []
        engine = _get_ocr_engine()
        if engine is None:
            print("未安装 OCR 依赖，请运行 pip install rapidocr_onnxruntime 后重试")
            return None
        try:
            if OCR_BACKEND in ('rapidocr', 'rapidocr_onnxruntime'):
                # RapidOCR：result 形如 [[box, text, score], ...]，兼容新旧 API 返回
                raw = engine(img)
                if isinstance(raw, tuple):
                    raw = raw[0] if raw else None
                raw_results = raw if raw else []
            elif OCR_BACKEND == 'pytesseract':
                import pytesseract
                # pytesseract 需要 PIL Image 输入：前面 np.array 转成 numpy 数组时需转回
                try:
                    from PIL import Image
                    if not isinstance(img, Image.Image):
                        img = Image.fromarray(img)
                except Exception as e:
                    print(f"OCR 图像转换失败: {e}")
                    return None
                data = pytesseract.image_to_data(img, lang='chi_sim+eng',
                                                 output_type=pytesseract.Output.DICT)
                n_blocks = len(data.get('text', []))
                for i in range(n_blocks):
                    text = str(data['text'][i]).strip()
                    if not text:
                        continue
                    try:
                        conf = float(data['conf'][i])
                    except (TypeError, ValueError):
                        conf = -1.0
                    if conf < 0:
                        continue
                    x = int(data['left'][i]); y = int(data['top'][i])
                    w = int(data['width'][i]); h = int(data['height'][i])
                    if w <= 0 or h <= 0:
                        continue
                    box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                    raw_results.append([box, text, conf / 100.0])
        except Exception as e:
            print(f"OCR 识别失败: {e}")
            return None
        # 解析每个文字块为统一结构（含中心坐标）
        # region 模式下截图是局部图，需先按 sx 还原缩放，再加 region 屏幕偏移得到真实坐标
        region_off_x = region_tuple[0] if region_tuple else 0
        region_off_y = region_tuple[1] if region_tuple else 0
        results = []
        for item in raw_results:
            try:
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                box, text, score = item[0], str(item[1]), item[2]
                xs = [float(p[0]) * sx for p in box]
                ys = [float(p[1]) * sx for p in box]
                x = int(min(xs)) + region_off_x
                y = int(min(ys)) + region_off_y
                w = int(max(xs) - min(xs)); h = int(max(ys) - min(ys))
                score = float(score)
                if score < float(min_score):
                    continue
                results.append({'text': text, 'x': x, 'y': y, 'w': w, 'h': h,
                                'cx': int(x + w / 2), 'cy': int(y + h / 2), 'score': score})
            except Exception:
                continue
        # 阅读顺序排序：cy 贪心聚类分行、行内按 cx 排序
        results.sort(key=lambda r: r['cy'])
        lines = []
        for r in results:
            if not lines:
                lines.append([r])
                continue
            last_line = lines[-1]
            avg_cy = sum(x['cy'] for x in last_line) / len(last_line)
            avg_h = sum(x['h'] for x in last_line) / len(last_line)
            threshold = max(avg_h * 0.6, 8)
            if abs(r['cy'] - avg_cy) <= threshold:
                last_line.append(r)
            else:
                lines.append([r])
        sorted_results = []
        for line in lines:
            sorted_results.extend(sorted(line, key=lambda x: x['cx']))
        print(f"[OCR] 识别到 {len(sorted_results)} 个文字块")
        for r in sorted_results:
            print(f"{r['text']} ({r['x']},{r['y']},{r['w']},{r['h']}) 置信度 {r['score']:.3f}")
        return sorted_results

    def _match_ocr_text(results, text, occurrence=1):
        """在 OCR 结果中按文字内容匹配目标块（先精确匹配，无结果再包含匹配），
        按 occurrence 取第 N 个（-1 表示最后一个），序号按阅读顺序"""
        if not results:
            return None
        target_text = str(text)
        matched = [r for r in results if r['text'] == target_text]
        if not matched:
            matched = [r for r in results if target_text in r['text']]
        if not matched:
            return None
        try:
            occ = int(occurrence)
        except (TypeError, ValueError):
            occ = 1
        if occ == -1:
            return matched[-1]
        if occ < 1:
            occ = 1
        if occ > len(matched):
            return matched[-1] if matched else None
        return matched[occ - 1]

    def map_key(key_str):
        # 本引擎统一走 pyautogui，键名一律返回小写字符串，避免把 pynput Key 对象传给 pyautogui
        return str(key_str).lower()
    
    def check_pause():
        while paused.is_set():
            if stop_event.is_set():
                return False
            time.sleep(0.05)
        return not stop_event.is_set()
    
    def wait_interruptible(duration):
        start = time.time()
        while time.time() - start < duration:
            if stop_event.is_set():
                return False
            if paused.is_set():
                paused_start = time.time()
                while paused.is_set():
                    if stop_event.is_set():
                        return False
                    time.sleep(0.05)
                start += time.time() - paused_start
            time.sleep(0.01)
        return True
    
    def execute_actions(actions):
        # 变量系统
        script_vars = {
            'screen_w': 1920, 'screen_h': 1080,
            'last_click_x': 0, 'last_click_y': 0,
            'last_move_x': 0, 'last_move_y': 0,
            'mouse_x': 0, 'mouse_y': 0,
            'loop_index': 0,
        }
        
        def _update_vars():
            try:
                w, h = pyautogui.size()
                script_vars['screen_w'] = w
                script_vars['screen_h'] = h
            except:
                pass
            try:
                pos = pyautogui.position()
                script_vars['mouse_x'] = pos.x
                script_vars['mouse_y'] = pos.y
            except:
                pass
        
        def _resolve(val):
            if not isinstance(val, str):
                return val
            pat = re.compile(r'\{\{(.+?)\}\}')
            m = pat.fullmatch(val)
            if m:
                expr = m.group(1).strip()
                ctx = dict(script_vars)
                ctx.update({'random': random, 'math': math, 'abs': abs, 'min': min, 'max': max, 'int': int, 'float': float, 'str': str})
                try:
                    return _safe_eval_template(expr, ctx)
                except Exception as e:
                    print(f"变量求值错误: {e}")
                    return val
            def _sub(m):
                try:
                    return str(_safe_eval_template(m.group(1).strip(), dict(script_vars, random=random, math=math, abs=abs, min=min, max=max, int=int, float=float, str=str)))
                except Exception as e:
                    print(f"变量求值错误: {e}")
                    return m.group(0)
            return pat.sub(_sub, val)
        
        def _resolve_kwargs(kwargs):
            return {k: _resolve(v) for k, v in kwargs.items()}
        
        def _update_after(atype, kw):
            _update_vars()
            if atype in ('click', 'double_click', 'right_click', 'left_click'):
                try:
                    pos = pyautogui.position()
                    script_vars['last_click_x'] = pos.x
                    script_vars['last_click_y'] = pos.y
                except:
                    pass
            elif atype == 'move':
                script_vars['last_move_x'] = kw.get('x', 0)
                script_vars['last_move_y'] = kw.get('y', 0)
                script_vars['last_click_x'] = kw.get('x', 0)
                script_vars['last_click_y'] = kw.get('y', 0)
            elif atype == 'move_rel':
                dx = kw.get('dx', 0)
                dy = kw.get('dy', 0)
                script_vars['last_move_x'] = script_vars.get('last_move_x', 0) + dx
                script_vars['last_move_y'] = script_vars.get('last_move_y', 0) + dy
                script_vars['last_click_x'] = script_vars['last_move_x']
                script_vars['last_click_y'] = script_vars['last_move_y']
            elif atype == 'drag':
                script_vars['last_move_x'] = kw.get('x', 0)
                script_vars['last_move_y'] = kw.get('y', 0)
        
        # 首轮执行前先刷新屏幕/鼠标变量，保证首个动作引用 {{screen_w}} 等时即为真实值
        _update_vars()
        
        for idx, action in enumerate(actions):
            if stop_event.is_set():
                return
            if not check_pause():
                return
            
            # 跳过禁用动作
            if not action.get('enabled', True):
                continue
            
            atype = action['type']
            kw = action.get('kwargs', {})
            kw = _resolve_kwargs(kw)
            
            # 更新UI状态
            status_msg['action'] = atype
            status_msg['action_idx'] = idx + 1
            
            try:
                if atype == 'move':
                    pyautogui.moveTo(kw.get('x', 0), kw.get('y', 0), duration=kw.get('duration', 0))
                elif atype == 'move_rel':
                    pyautogui.moveRel(kw.get('dx', 0), kw.get('dy', 0), duration=kw.get('duration', 0))
                elif atype == 'locate_click':
                    img_path = kw.get('image_path', '')
                    if not os.path.exists(img_path):
                        print(f"图像识别: 图片不存在 {img_path}")
                    conf = kw.get('confidence', 0.9)
                    offx = kw.get('offset_x', 0)
                    offy = kw.get('offset_y', 0)
                    btn = kw.get('button', 'left')
                    on_fail = kw.get('on_fail', 'skip')
                    max_attempts = 3 if on_fail == 'retry' else 1
                    clicked = False
                    for attempt in range(max_attempts):
                        if stop_event.is_set():
                            break
                        try:
                            loc = pyautogui.locateOnScreen(img_path, confidence=conf)
                            if loc:
                                center = pyautogui.center(loc)
                                pyautogui.click(x=center.x + offx, y=center.y + offy, button=btn, clicks=1, interval=0.1)
                                clicked = True
                                break
                        except:
                            pass
                        if on_fail == 'retry' and attempt < max_attempts - 1:
                            time.sleep(0.5)
                    if not clicked and on_fail == 'error' and not stop_event.is_set():
                        print(f"图像识别失败: {img_path}")
                elif atype == 'ocr_read':
                    # 屏幕文字 OCR 识别：截屏 → 识别 → 打印结果（供调试/观察）
                    region = kw.get('region') or None
                    min_score = float(kw.get('min_score', 0.5) or 0.5)
                    scale = float(kw.get('scale', 1.0) or 1.0)
                    _ocr_read(region=region, min_score=min_score, scale=scale)
                elif atype == 'ocr_click':
                    # 文字定位点击：OCR 按文字匹配定位并点击（与主程序 ocr_click 对齐）
                    text = str(kw.get('text', '') or '')
                    if not text:
                        print("OCR 文字定位: 未指定识别文字，跳过")
                        continue
                    occurrence = kw.get('occurrence', 1)
                    offx = int(kw.get('offset_x', 0) or 0)
                    offy = int(kw.get('offset_y', 0) or 0)
                    region = kw.get('region') or None
                    min_score = float(kw.get('min_score', 0.5) or 0.5)
                    on_fail = kw.get('on_fail', 'skip')
                    max_attempts = 3 if on_fail == 'retry' else 1
                    clicked = False
                    for attempt in range(max_attempts):
                        if stop_event.is_set():
                            break
                        results = _ocr_read(region=region, min_score=min_score)
                        if results is None:
                            # OCR 依赖未安装或识别失败：按失败处理
                            if on_fail == 'error' and not stop_event.is_set():
                                raise RuntimeError(f"OCR 文字定位失败: {text}（OCR 不可用）")
                            print(f"OCR 文字定位: OCR 不可用，无法查找 {text}")
                            break
                        target = _match_ocr_text(results, text, occurrence)
                        if target is not None:
                            tx = target['cx'] + offx
                            ty = target['cy'] + offy
                            pyautogui.click(x=tx, y=ty, button='left', clicks=1, interval=0.1)
                            print(f"OCR 文字定位: 已点击 '{text}' 位置({tx}, {ty}) 置信度 {target['score']:.3f}")
                            clicked = True
                            break
                        print(f"OCR 文字定位: 未找到 '{text}' (尝试 {attempt + 1}/{max_attempts})")
                        if on_fail == 'retry' and attempt < max_attempts - 1:
                            time.sleep(0.5)
                    if not clicked and on_fail == 'error' and not stop_event.is_set():
                        raise RuntimeError(f"OCR 文字定位失败: 未找到文字 '{text}'")
                elif atype == 'click':
                    pyautogui.click(button=kw.get('button', 'left'), clicks=kw.get('clicks', 1), interval=kw.get('interval', 0.1))
                elif atype == 'double_click':
                    pyautogui.click(button=kw.get('button', 'left'), clicks=2, interval=0.1)
                elif atype == 'right_click':
                    pyautogui.rightClick()
                elif atype == 'left_click':
                    pyautogui.leftClick()
                elif atype == 'scroll':
                    direction = kw.get('direction', 'vertical')
                    if direction == 'horizontal':
                        pyautogui.hscroll(kw.get('clicks', 0))
                    else:
                        pyautogui.scroll(kw.get('clicks', 0))
                elif atype == 'press':
                    key = map_key(kw.get('key', ''))
                    pyautogui.press(key, presses=kw.get('presses', 1), interval=kw.get('interval', 0.1))
                elif atype == 'type':
                    pyautogui.typewrite(kw.get('text', ''), interval=kw.get('interval', 0.1))
                elif atype == 'hotkey':
                    keys = kw.get('keys', [])
                    pyautogui.hotkey(*keys)
                elif atype == 'drag':
                    pyautogui.dragTo(kw.get('x', 0), kw.get('y', 0), duration=kw.get('duration', 0), button=kw.get('button', 'left'))
                elif atype == 'wait':
                    wt = kw.get('wait_type', 'time')
                    if wt == 'time':
                        wait_interruptible(kw.get('seconds', 1))
                    elif wt == 'image':
                        target_img = kw.get('target_image', '')
                        timeout = kw.get('timeout', 30)
                        start = time.time()
                        found = False
                        while time.time() - start < timeout:
                            if stop_event.is_set():
                                break
                            try:
                                loc = pyautogui.locateOnScreen(target_img, confidence=0.8)
                                if loc:
                                    found = True
                                    break
                            except:
                                pass
                            time.sleep(0.5)
                        if not found and not stop_event.is_set():
                            print(f"等待图片超时: {target_img}")
                    elif wt == 'window':
                        keyword = kw.get('target_window', '')
                        timeout = kw.get('timeout', 30)
                        start = time.time()
                        found = False
                        while time.time() - start < timeout:
                            if stop_event.is_set():
                                break
                            try:
                                import ctypes
                                from ctypes import wintypes
                                titles = []
                                def _cb(hwnd, _):
                                    if ctypes.windll.user32.IsWindowVisible(hwnd):
                                        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                                        if length > 0:
                                            buf = ctypes.create_unicode_buffer(length + 1)
                                            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                                            titles.append(buf.value)
                                    return True
                                EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                                ctypes.windll.user32.EnumWindows(EnumWindowsProc(_cb), 0)
                                kw_lower = keyword.lower()
                                for t in titles:
                                    if kw_lower in t.lower():
                                        found = True
                                        break
                                if found:
                                    break
                            except:
                                pass
                            time.sleep(0.5)
                        if not found and not stop_event.is_set():
                            print(f"等待窗口超时: {keyword}")
                    elif wt == 'clipboard':
                        target_txt = kw.get('target_text', '')
                        timeout = kw.get('timeout', 30)
                        start = time.time()
                        found = False
                        while time.time() - start < timeout:
                            if stop_event.is_set():
                                break
                            try:
                                import pyperclip
                                current = pyperclip.paste() or ''
                                if target_txt:
                                    if target_txt in current:
                                        found = True
                                        break
                                else:
                                    if current.strip():
                                        found = True
                                        break
                            except:
                                pass
                            time.sleep(0.3)
                        if not found and not stop_event.is_set():
                            print("等待剪贴板超时")
                    elif wt == 'key':
                        target_k = kw.get('target_key', '')
                        timeout = kw.get('timeout', 30)
                        key_pressed = threading.Event()
                        def on_wait_key(key):
                            try:
                                ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                            except:
                                ks = str(key).lower()
                            if ks == target_k.lower():
                                key_pressed.set()
                                return False
                            return True
                        listener = KeyboardListener(on_press=on_wait_key)
                        listener.start()
                        start = time.time()
                        while not key_pressed.is_set() and time.time() - start < timeout and not stop_event.is_set():
                            time.sleep(0.05)
                        listener.stop()
                        if not key_pressed.is_set() and not stop_event.is_set():
                            print(f"等待按键超时: {target_k}")
                elif atype == 'hold':
                    pyautogui.mouseDown(button=kw.get('button', 'left'))
                    wait_interruptible(kw.get('duration', 1))
                    pyautogui.mouseUp(button=kw.get('button', 'left'))
                elif atype == 'key_hold':
                    pyautogui.keyDown(kw.get('key', ''))
                    wait_interruptible(kw.get('duration', 1))
                    pyautogui.keyUp(kw.get('key', ''))
                elif atype == 'fill':
                    # 与主程序一致：每次执行只填 1 个数字，通过 script_vars 内存进度续传，
                    # 不自动按回车（回车由动作序列中的 press 动作自行控制）
                    total = int(kw.get('total_digits', 4) or 4)
                    start_n = int(kw.get('start', 0) or 0)
                    end_n = int(kw.get('end', 9999) or 9999)
                    prefix = str(kw.get('prefix', '') or '')
                    suffix = str(kw.get('suffix', '') or '')
                    fill_interval = float(kw.get('interval', 0.1) or 0.1)
                    fixed_part_len = len(prefix) + len(suffix)
                    if fixed_part_len >= total:
                        raise ValueError(f"前缀+后缀长度({fixed_part_len})不能大于等于总位数({total})")
                    fill_digits = total - fixed_part_len
                    max_val = 10 ** fill_digits - 1
                    cur = int(script_vars.get('fill_current', start_n))
                    if cur > max_val:
                        cur = 0
                    if cur > end_n:
                        cur = start_n
                    text = prefix + str(cur).zfill(fill_digits) + suffix
                    status_msg['action'] = f"fill {cur}"
                    pyautogui.typewrite(text, interval=0.05)
                    script_vars['fill_current'] = cur + 1
                    if fill_interval > 0.05:
                        if not wait_interruptible(fill_interval - 0.05):
                            break
                elif atype == 'open_file':
                    os.startfile(kw.get('filepath', ''))
                elif atype == 'open_url':
                    import webbrowser
                    webbrowser.open(kw.get('url', ''), new=2)
                elif atype == 'multi_key':
                    keys = kw.get('keys', []) or []
                    dur = kw.get('duration', 1.0) or 1.0
                    for k in keys:
                        pyautogui.keyDown(map_key(k))
                    if not wait_interruptible(dur):
                        for k in reversed(keys):
                            pyautogui.keyUp(map_key(k))
                        break
                    for k in reversed(keys):
                        pyautogui.keyUp(map_key(k))
                elif atype == 'multi_mouse':
                    buttons = kw.get('buttons', []) or []
                    dur = kw.get('duration', 1.0) or 1.0
                    for b in buttons:
                        pyautogui.mouseDown(button=b)
                    if not wait_interruptible(dur):
                        for b in reversed(buttons):
                            pyautogui.mouseUp(button=b)
                        break
                    for b in reversed(buttons):
                        pyautogui.mouseUp(button=b)
                elif atype == 'multi_key_mouse':
                    keys = kw.get('keys', []) or []
                    buttons = kw.get('buttons', []) or []
                    dur = kw.get('duration', 1.0) or 1.0
                    for k in keys:
                        pyautogui.keyDown(map_key(k))
                    for b in buttons:
                        pyautogui.mouseDown(button=b)
                    if not wait_interruptible(dur):
                        for b in reversed(buttons):
                            pyautogui.mouseUp(button=b)
                        for k in reversed(keys):
                            pyautogui.keyUp(map_key(k))
                        break
                    for b in reversed(buttons):
                        pyautogui.mouseUp(button=b)
                    for k in reversed(keys):
                        pyautogui.keyUp(map_key(k))
                elif atype == 'loop':
                    sub = kw.get('sub_actions', []) or []
                    rep = int(kw.get('repeat', -1))
                    ival = kw.get('interval', 0.5) or 0.5
                    count = 0
                    while True:
                        if stop_event.is_set() or not check_pause():
                            break
                        script_vars['loop_index'] = count
                        execute_actions(sub)
                        count += 1
                        if rep > 0 and count >= rep:
                            break
                        if ival > 0 and not wait_interruptible(ival):
                            break
                elif atype == 'conditional':
                    _run_conditional(kw)
                else:
                    print(f"执行动作 {atype} 时出错: 未知的动作类型（该导出版本不支持此动作，请在主程序导出前检查）")
                _update_after(atype, kw)
            except Exception as e:
                print(f"执行动作 {atype} 时出错: {e}")
    
    def _run_conditional(kw):
        """执行条件触发动作：等待指定条件满足后执行子动作
        支持条件类型：keyboard/press, click/right_click/left_click, double_click, scroll,
        move, hold, key_hold, hotkey, type(剪贴板), fill(剪贴板数字),
        open_url_listen(剪贴板URL), open_file_listen(文件监听), wait(延时)
        """
        if not PYNPUT_AVAILABLE:
            print("条件触发动作需要 pynput 支持，当前环境中不可用，跳过该动作")
            return
        sub = kw.get('sub_actions', []) or []
        ctype = kw.get('condition_type', 'keyboard')
        tkeys = kw.get('target_keys') or ([kw.get('target_key')] if kw.get('target_key') else [])
        tx = kw.get('target_x', 0) or 0
        ty = kw.get('target_y', 0) or 0
        dur = kw.get('duration', 1.0) or 1.0
        if ctype == 'mouse':
            ctype = 'click'
        triggered = threading.Event()

        def _run_subs():
            execute_actions(sub)

        def _wait_listener(lst):
            while lst.is_alive() and not stop_event.is_set() and not triggered.is_set():
                time.sleep(0.01)
            try:
                lst.stop()
            except Exception:
                pass
            if triggered.is_set() and not stop_event.is_set() and check_pause():
                _run_subs()

        def _wait_poll():
            while not triggered.is_set() and not stop_event.is_set():
                time.sleep(0.01)
            if triggered.is_set() and not stop_event.is_set() and check_pause():
                _run_subs()

        if ctype in ('keyboard', 'press'):
            tl = [str(k).lower() for k in tkeys]

            def on_press(key):
                try:
                    ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except Exception:
                    ks = str(key).lower()
                if ks in tl:
                    triggered.set()
                    return False
                return True

            listener = KeyboardListener(on_press=on_press)
            listener.start()
            _wait_listener(listener)
        elif ctype in ('click', 'right_click', 'left_click'):
            tl = [str(k).lower() for k in tkeys]

            def on_click(x, y, button, pressed):
                if pressed:
                    bn = str(button).split('.')[-1].lower()
                    if bn in tl:
                        triggered.set()
                        return False
                return True

            listener = mouse.Listener(on_click=on_click)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'double_click':
            last_btn = [None, 0.0]
            tl = [str(k).lower() for k in tkeys]

            def on_click(x, y, button, pressed):
                if pressed:
                    bn = str(button).split('.')[-1].lower()
                    now = time.time()
                    if (not tl or bn in tl) and last_btn[0] == bn and now - last_btn[1] < 0.4:
                        triggered.set()
                        return False
                    last_btn[0] = bn
                    last_btn[1] = now
                return True

            listener = mouse.Listener(on_click=on_click)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'scroll':
            direction = str(tkeys[0]).lower() if tkeys else 'up'

            def on_scroll(x, y, dx, dy):
                if (direction == 'up' and dy > 0) or (direction == 'down' and dy < 0) \
                   or (direction == 'left' and dx < 0) or (direction == 'right' and dx > 0):
                    triggered.set()
                    return False
                return True

            listener = mouse.Listener(on_scroll=on_scroll)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'move':
            th = 20

            def on_move(x, y):
                if abs(x - tx) <= th and abs(y - ty) <= th:
                    triggered.set()
                    return False
                return True

            listener = mouse.Listener(on_move=on_move)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'hold':
            target_btn = str(tkeys[0]).lower() if tkeys else 'left'
            press_t = {'t': 0.0}

            def on_click(x, y, button, pressed):
                bn = str(button).split('.')[-1].lower()
                if bn == target_btn:
                    if pressed:
                        press_t['t'] = time.time()
                    elif press_t['t'] > 0 and time.time() - press_t['t'] >= dur:
                        triggered.set()
                        return False
                return True

            listener = mouse.Listener(on_click=on_click)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'key_hold':
            target_k = str(tkeys[0]).lower() if tkeys else ''
            press_t = {'t': 0.0}

            def on_press(key):
                try:
                    ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except Exception:
                    ks = str(key).lower()
                if ks == target_k:
                    press_t['t'] = time.time()

            def on_release(key):
                if press_t['t'] > 0 and time.time() - press_t['t'] >= dur:
                    triggered.set()
                    return False
                press_t['t'] = 0.0
                return True

            listener = KeyboardListener(on_press=on_press, on_release=on_release)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'hotkey':
            hl = [str(k).strip().lower() for k in str(tkeys[0] if tkeys else '').split('+') if str(k).strip()]
            pressed_keys = set()

            def on_press(key):
                try:
                    ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except Exception:
                    ks = str(key).lower()
                pressed_keys.add(ks)
                if all(rk in pressed_keys for rk in hl):
                    triggered.set()
                    return False
                return True

            def on_release(key):
                try:
                    ks = key.char.lower() if hasattr(key, 'char') and key.char else key.name.lower()
                except Exception:
                    ks = str(key).lower()
                pressed_keys.discard(ks)
                return True

            listener = KeyboardListener(on_press=on_press, on_release=on_release)
            listener.start()
            _wait_listener(listener)
        elif ctype == 'type':
            target_text = str(tkeys[0]) if tkeys else ''
            last_clip = {'t': ''}
            try:
                import pyperclip
                last_clip['t'] = pyperclip.paste() or ''
            except Exception:
                pass

            def _poll():
                while not triggered.is_set() and not stop_event.is_set():
                    try:
                        import pyperclip
                        cur = pyperclip.paste() or ''
                        if cur != last_clip['t'] and target_text and target_text in cur:
                            triggered.set()
                            return
                        last_clip['t'] = cur
                    except Exception:
                        pass
                    time.sleep(0.3)

            threading.Thread(target=_poll, daemon=True).start()
            _wait_poll()
        elif ctype == 'fill':
            last_clip = {'t': ''}
            try:
                import pyperclip
                last_clip['t'] = pyperclip.paste() or ''
            except Exception:
                pass

            def _poll():
                while not triggered.is_set() and not stop_event.is_set():
                    try:
                        import pyperclip
                        cur = pyperclip.paste() or ''
                        if cur != last_clip['t'] and cur.strip().isdigit():
                            triggered.set()
                            return
                        last_clip['t'] = cur
                    except Exception:
                        pass
                    time.sleep(0.3)

            threading.Thread(target=_poll, daemon=True).start()
            _wait_poll()
        elif ctype == 'open_url_listen':
            url_kw = str(tkeys[0]) if tkeys else ''
            last_clip = {'t': ''}
            try:
                import pyperclip
                last_clip['t'] = pyperclip.paste() or ''
            except Exception:
                pass
            url_pat = re.compile(r'https?://\S+')

            def _poll():
                while not triggered.is_set() and not stop_event.is_set():
                    try:
                        import pyperclip
                        cur = pyperclip.paste() or ''
                        if cur != last_clip['t']:
                            urls = url_pat.findall(cur)
                            if (url_kw and any(url_kw in u for u in urls)) or (not url_kw and urls):
                                triggered.set()
                                return
                            last_clip['t'] = cur
                    except Exception:
                        pass
                    time.sleep(0.3)

            threading.Thread(target=_poll, daemon=True).start()
            _wait_poll()
        elif ctype == 'open_file_listen':
            monitor_path = str(tkeys[0]) if tkeys else ''
            monitor_mode = kw.get('monitor_mode', 'exists')

            def _poll():
                last_m = {'t': 0.0}
                if monitor_path and os.path.exists(monitor_path):
                    last_m['t'] = os.path.getmtime(monitor_path)
                    if monitor_mode == 'exists':
                        triggered.set()
                        return
                while not triggered.is_set() and not stop_event.is_set():
                    if not monitor_path:
                        triggered.set()
                        return
                    if os.path.exists(monitor_path):
                        if monitor_mode == 'exists':
                            triggered.set()
                            return
                        cm = os.path.getmtime(monitor_path)
                        if cm != last_m['t']:
                            triggered.set()
                            return
                        last_m['t'] = cm
                    time.sleep(0.5)

            threading.Thread(target=_poll, daemon=True).start()
            _wait_poll()
        elif ctype == 'wait':
            if wait_interruptible(dur) and not stop_event.is_set() and check_pause():
                _run_subs()
        else:
            print(f"条件触发: 不支持的条件类型 {ctype}")
    
    # ---------- 主流程：配置 → 控制面板 → runner，可循环进入（退格返回上一级） ----------
    while True:
        # 每轮会话重置状态，避免重入混乱（监听器/线程/事件均为本轮新实例）
        stop_event.clear()
        paused.clear()
        back_event.clear()
        status_msg.update({"state": "就绪", "loop": 0, "action": "", "total_loops": 1})

        # 初始配置
        run_info = show_config_dialog()
        if not run_info['confirmed']:
            print("已取消执行")
            return

        run_count = run_info['count']
        run_interval = run_info['interval']
        status_msg['total_loops'] = run_count if run_count > 0 else -1

        # 启动控制面板
        panel = show_control_panel()

        # 快捷键监听（随会话重建，支持自定义键名：按 char/name 动态匹配用户键名）
        listener = None
        if PYNPUT_AVAILABLE:
            def on_press(key):
                try:
                    if hasattr(key, 'char') and key.char:
                        kname = key.char.lower()
                    elif hasattr(key, 'name') and key.name:
                        kname = key.name.lower()
                    else:
                        kname = str(key).lower()
                except Exception:
                    try:
                        kname = str(key).lower()
                    except Exception:
                        kname = ''
                if kname and kname == hotkey_pause:
                    if paused.is_set():
                        paused.clear()
                        status_msg['state'] = "运行中"
                    else:
                        paused.set()
                        status_msg['state'] = "已暂停"
                elif kname and kname == hotkey_stop:
                    stop_event.set()
                    if paused.is_set():
                        paused.clear()
                    status_msg['state'] = "已停止"
                elif kname and kname == hotkey_back:
                    # 退格返回上一级：停止当前脚本并标记返回事件，UI 线程据此关闭面板
                    stop_event.set()
                    if paused.is_set():
                        paused.clear()
                    status_msg['state'] = "已停止"
                    back_event.set()
                return True  # 返回 True 保持监听器运行；停止由 listener.stop() 显式控制

            listener = KeyboardListener(on_press=on_press)
            listener.daemon = True
            listener.start()

        print(f"[提示] 运行中按 {hotkey_pause} 暂停/继续，按 {hotkey_stop} 停止，按 {hotkey_back} 返回上一级")
        status_msg['state'] = "运行中"

        # 后台线程执行脚本
        def _runner():
            loop_num = 0
            try:
                while True:
                    if stop_event.is_set():
                        break
                    if not check_pause():
                        break

                    loop_num += 1
                    status_msg['loop'] = loop_num
                    execute_actions(SCRIPT_DATA)

                    if run_count > 0 and loop_num >= run_count:
                        break
                    if run_interval > 0:
                        wait_interruptible(run_interval)

                if not stop_event.is_set():
                    status_msg['state'] = "已完成"
            except Exception as e:
                print(f"执行出错: {e}")
                status_msg['state'] = f"出错: {e}"
            finally:
                if listener:
                    try:
                        listener.stop()
                    except:
                        pass

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()

        # UI 主循环
        panel.mainloop()

        # 窗口关闭时确保停止
        stop_event.set()
        if paused.is_set():
            paused.clear()
        thread.join(timeout=2)
        if listener:
            try:
                listener.stop()
            except:
                pass

        # 退格返回上一级 → 重新弹出初始配置界面（可改参数后再次运行）
        if back_event.is_set():
            back_event.clear()
            print("[提示] 返回上一级，重新弹出配置界面")
            continue
        else:
            break

if __name__ == '__main__':
    # Windows DPI 感知（缩放感知）：确保高 DPI 缩放下
    # pyautogui.screenshot 像素坐标与 pyautogui.click 逻辑坐标一致，避免 region OCR 定位漂移
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    print("=" * 40)
    print("  自动化脚本 - 独立可执行版")
    print("=" * 40)
    run_script()
'''.replace('__SCRIPT_DATA__', repr(data_json))

    def _generate_launcher_code(self):
        return self._build_launcher_full_code(
            json.dumps(self.autoclicker.actions, ensure_ascii=False))

    def export_to_python(self):
        if not self.autoclicker.actions:
            messagebox.showwarning("提示", "当前没有任何动作，请先添加动作后再导出。", parent=self.window)
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
            title="导出Python文件"
        )
        if not filename:
            return
        
        try:
            code = self._generate_launcher_code()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(code)
            messagebox.showinfo("导出成功", 
                              f"Python文件已保存到:\n{filename}\n\n可直接运行:\npython \"{filename}\"", 
                              parent=self.window)
        except Exception as e:
            messagebox.showerror("导出失败", f"保存文件失败: {e}", parent=self.window)
    
    def export_to_exe(self):
        if not self.autoclicker.actions:
            messagebox.showwarning("提示", "当前没有任何动作，请先添加动作后再导出。", parent=self.window)
            return
        
        try:
            import PyInstaller
            pyinstaller_version = PyInstaller.__version__
        except ImportError:
            response = messagebox.askyesno("缺少 PyInstaller",
                "导出可执行文件需要 PyInstaller 库。\n\n"
                "是否立即安装？\n"
                "(安装过程可能需要几分钟，需要网络连接)",
                parent=self.window)
            if response:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "pyinstaller",
                         "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                        capture_output=True, text=True,
                        encoding='utf-8', errors='replace', timeout=300
                    )
                    if result.returncode != 0:
                        messagebox.showerror("安装失败",
                            f"PyInstaller 安装失败:\n{result.stderr}", parent=self.window)
                        return
                except Exception as e:
                    messagebox.showerror("安装失败", f"安装 PyInstaller 时出错:\n{e}", parent=self.window)
                    return
            else:
                return
        
        export_dialog = tk.Toplevel(self.window)
        export_dialog.title("导出EXE")
        export_dialog.transient(self.window)
        export_dialog.grab_set()
        export_dialog.resizable(True, True)
        export_dialog.minsize(420, 370)
        
        main_frame = ttk.Frame(export_dialog, padding=self.PAD_MD)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="导出设置", font=self.FONT_HEADING).pack(anchor='w', pady=(0, self.PAD_SM))
        
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill='x', pady=self.PAD_XS)
        ttk.Label(name_frame, text="文件名:").pack(side='left')
        name_var = tk.StringVar(value="自动化脚本")
        name_entry = ttk.Entry(name_frame, textvariable=name_var, width=30)
        name_entry.pack(side='left', padx=self.PAD_XS, fill='x', expand=True)
        ttk.Label(name_frame, text=".exe").pack(side='left')
        
        console_var = tk.BooleanVar(value=True)
        console_frame = ttk.Frame(main_frame)
        console_frame.pack(fill='x', pady=self.PAD_XS)
        ttk.Checkbutton(console_frame, text="显示控制台窗口(用于调试)", variable=console_var).pack(anchor='w')
        
        single_var = tk.BooleanVar(value=True)
        single_frame = ttk.Frame(main_frame)
        single_frame.pack(fill='x', pady=self.PAD_XS)
        ttk.Checkbutton(single_frame, text="打包为单个文件(推荐)", variable=single_var).pack(anchor='w')
        
        admin_var = tk.BooleanVar(value=False)
        admin_frame = ttk.Frame(main_frame)
        admin_frame.pack(fill='x', pady=self.PAD_XS)
        ttk.Checkbutton(admin_frame, text="请求管理员权限(UAC提权)", variable=admin_var).pack(anchor='w')
        
        status_var = tk.StringVar(value="准备就绪")
        status_label = ttk.Label(main_frame, textvariable=status_var, foreground=self.COLOR_TEXT_SECONDARY)
        status_label.pack(anchor='w', pady=(self.PAD_SM, 0))
        
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100, length=380, mode='indeterminate')
        progress_bar.pack(fill='x', pady=(self.PAD_XS, 0))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(self.PAD_SM, 0))
        
        export_btn = ttk.Button(btn_frame, text="\U0001F4E6 开始导出")
        cancel_btn = ttk.Button(btn_frame, text="取消", command=export_dialog.destroy)
        export_btn.pack(side='left', padx=self.PAD_XS)
        cancel_btn.pack(side='right', padx=self.PAD_XS)
        
        def do_export():
            try:
                exe_name = name_var.get().strip()
                if not exe_name:
                    messagebox.showwarning("提示", "请输入文件名", parent=export_dialog)
                    return
                
                exe_name = re.sub(r'[\\/:*?"<>|]', '', exe_name)
                
                export_btn.config(state='disabled')
                status_var.set("正在保存脚本数据...")
                export_dialog.update()
                
                _tmp_dir = tempfile.mkdtemp(prefix='auto_clicker_export_')
                
                status_var.set("正在生成启动脚本...")
                export_dialog.update()
                
                launcher_code = self._build_launcher_full_code(
                    json.dumps(self.autoclicker.actions, ensure_ascii=False))
                
                launcher_path = os.path.join(_tmp_dir, "_export_launcher.py")
                with open(launcher_path, 'w', encoding='utf-8') as f:
                    f.write(launcher_code)
                
                status_var.set("正在调用 PyInstaller 打包...")
                progress_var.set(0)
                export_dialog.update()
                
                output_dir = filedialog.askdirectory(
                    title="选择 EXE 输出目录",
                    parent=export_dialog
                )
                if not output_dir:
                    status_var.set("已取消导出")
                    progress_bar.stop()
                    progress_var.set(0)
                    export_btn.config(state='normal')
                    shutil.rmtree(_tmp_dir, ignore_errors=True)
                    return
                
                cmd = [
                    sys.executable, "-m", "PyInstaller",
                    "--noconfirm",
                    "--distpath", output_dir,
                    "--workpath", os.path.join(_tmp_dir, "_pyinstaller_build"),
                    "--specpath", _tmp_dir,
                ]

                for _ex_mod in ("numpy", "matplotlib", "pandas", "scipy", "cv2", "sklearn", "PyQt5", "PySide2"):
                    cmd.append("--exclude-module")
                    cmd.append(_ex_mod)

                if single_var.get():
                    cmd.append("--onefile")
                
                if not console_var.get():
                    cmd.append("--noconsole")
                else:
                    cmd.append("--console")
                
                if admin_var.get():
                    cmd.append("--uac-admin")
                
                cmd.append("--name")
                cmd.append(exe_name)
                cmd.append(launcher_path)
                
                status_var.set("正在分析依赖...")
                progress_var.set(5)
                export_dialog.update()
                
                def _safe_update(value, msg):
                    try:
                        if export_dialog.winfo_exists():
                            def _do():
                                status_var.set(msg)
                            export_dialog.after(0, _do)
                    except:
                        pass
                
                def _on_complete(success, msg, is_error=False):
                    try:
                        if export_dialog.winfo_exists():
                            progress_bar.stop()
                            progress_var.set(100 if success else 0)
                            status_var.set(msg)
                            export_btn.config(state='normal')
                            if success:
                                exe_path = os.path.join(output_dir, f"{exe_name}.exe")
                                if os.path.exists(exe_path):
                                    messagebox.showinfo("导出成功",
                                        f"可执行文件已生成:\n{exe_path}\n\n"
                                        f"文件大小: {os.path.getsize(exe_path) / 1024 / 1024:.1f} MB",
                                        parent=export_dialog)
                                else:
                                    messagebox.showwarning("提示",
                                        "打包已完成但未在输出目录找到 EXE 文件，请检查 dist 文件夹。",
                                        parent=export_dialog)
                            elif is_error:
                                messagebox.showerror("导出失败",
                                    f"PyInstaller 打包失败:\n\n{msg}",
                                    parent=export_dialog)
                    except:
                        pass
                    shutil.rmtree(_tmp_dir, ignore_errors=True)
                
                progress_bar.start(30)
                
                def _run_packaging():
                    try:
                        proc = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            encoding='utf-8', errors='replace'
                        )
                        
                        current_progress = 5
                        line_count = 0
                        output_lines = []
                        stage_keywords = {
                            'Analyzing': (10, '正在分析脚本...'),
                            'Loading module hook': (22, '正在加载模块...'),
                            'Collecting': (38, '正在收集依赖...'),
                            'Copying': (55, '正在复制文件...'),
                            'Building EXE because': (75, '正在构建 EXE...'),
                            'Building EXE completed': (92, '正在完成打包...'),
                        }
                        
                        for line in proc.stdout:
                            line = line.strip()
                            output_lines.append(line)
                            line_count += 1
                            matched = False
                            for keyword, (prog, msg) in stage_keywords.items():
                                if keyword in line:
                                    current_progress = max(current_progress, prog)
                                    _safe_update(current_progress, msg)
                                    matched = True
                                    break
                            if not matched and line_count % 10 == 0:
                                current_progress = min(current_progress + 1, 90)
                                _safe_update(current_progress, status_var.get())
                        
                        proc.wait()
                        
                        if proc.returncode == 0:
                            _safe_update(100, "导出成功!")
                            export_dialog.after(100, lambda: _on_complete(True, "导出成功!"))
                        else:
                            error_output = '\n'.join(output_lines[-20:])
                            _safe_update(0, "导出失败")
                            export_dialog.after(100, lambda m=error_output: _on_complete(False, m, True))
                    except Exception as e:
                        _safe_update(0, "导出出错")
                        export_dialog.after(100, lambda m=str(e): _on_complete(False, m, True))
                
                threading.Thread(target=_run_packaging, daemon=True).start()
                
            except Exception as e:
                status_var.set("导出出错")
                progress_bar.stop()
                progress_var.set(0)
                messagebox.showerror("错误", f"导出过程中出错:\n{e}", parent=export_dialog)
                export_btn.config(state='normal')
        
        export_btn.config(command=do_export)
    
    def toggle_safety(self):
        if self.safety_var.get():
            pyautogui.FAILSAFE = True
        else:
            pyautogui.FAILSAFE = False
            messagebox.showwarning(
                "安全提示",
                "已关闭自动防误触保护（FAILSAFE）。\n"
                "鼠标移到屏幕左上角时不再触发紧急停止，请谨慎操作。",
                parent=self.window)
    
    def minimize_to_tray(self):
        if PYSTRAY_AVAILABLE and self.tray_icon:
            self.window.withdraw()
            self.is_hidden = True
            
            if not hasattr(self, 'tray_thread') or not self.tray_thread.is_alive():
                self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                self.tray_thread.start()
        else:
            self.window.iconify()
    
    def show_window(self):
        if self.is_hidden:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self.is_hidden = False
            
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except:
                    pass
        else:
            self.window.deiconify()
    
    def toggle_window_visibility(self):
        if self.window.winfo_viewable():
            self.minimize_to_tray()
        else:
            self.show_window()
    
    def on_closing(self):
        self.clear_position_cache()
        self.quit_application()
    
    def _switch_tab(self, idx):
        old_idx = self.current_tab
        self.nav_buttons[old_idx].configure(
            background=self.COLOR_BG if not self.dark_mode else self.DARK_COLOR_BG,
            foreground=self.COLOR_TEXT)
        self.nav_indicators[old_idx].configure(bg=self.COLOR_BG if not self.dark_mode else self.DARK_COLOR_BG)
        
        self.current_tab = idx
        self.nav_buttons[idx].configure(
            background=self.COLOR_PRIMARY_LIGHT if not self.dark_mode else self.DARK_COLOR_CARD_ALT,
            foreground=self.COLOR_PRIMARY)
        self.nav_indicators[idx].configure(bg=self.COLOR_PRIMARY)
        
        for i, frame in enumerate(self.tab_frames):
            if i == idx:
                frame.pack(fill='both', expand=True)
            else:
                frame.pack_forget()
    
    def _create_status_bar(self):
        self.status_bar = ttk.Frame(self.window, height=28, relief='sunken', borderwidth=1)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky='ew')
        self.status_bar.grid_propagate(False)
        self.status_bar.grid_columnconfigure(0, weight=1)
        self.status_bar.grid_columnconfigure(1, weight=0)
        self.status_bar.grid_columnconfigure(2, weight=0)
        self.status_bar.grid_columnconfigure(3, weight=0)
        
        self.mouse_label = ttk.Label(self.status_bar, text="鼠标: X=?, Y=?", 
                                     font=self.FONT_SMALL)
        self.mouse_label.pack(side='left', padx=self.PAD_SM)
        
        self.action_count_label = ttk.Label(self.status_bar, text="动作数: 0", 
                                            font=self.FONT_SMALL)
        self.action_count_label.pack(side='left', padx=self.PAD_MD)
        
        self.disabled_count_label = ttk.Label(self.status_bar, text="禁用: 0", 
                                              font=self.FONT_SMALL, foreground='gray')
        self.disabled_count_label.pack(side='left', padx=self.PAD_MD)
        
        self.elapsed_label = ttk.Label(self.status_bar, text="耗时: --", 
                                       font=self.FONT_SMALL)
        self.elapsed_label.pack(side='left', padx=self.PAD_MD)
        
        self.undo_label = ttk.Label(self.status_bar, text="撤销: 0 | 重做: 0", 
                                    font=self.FONT_SMALL, foreground='gray')
        self.undo_label.pack(side='left', padx=self.PAD_MD)
        
        self.status_indicator = ttk.Label(self.status_bar, text=self.ICON_RED_CIRCLE + " 停止", 
                                          font=self.FONT_SMALL, foreground=self.COLOR_DANGER)
        self.status_indicator.pack(side='right', padx=self.PAD_SM)
        
        self.sizegrip = ttk.Sizegrip(self.status_bar)
        self.sizegrip.pack(side='right')
        
        self._exec_start_time = None
        self._exec_elapsed = 0
        
        self._update_status_bar()
    
    def _update_status_bar(self):
        try:
            self._refresh_mouse_pos()
            self.mouse_label.config(text=f"鼠标: X={self.mouse_x}, Y={self.mouse_y}")
            count = len(self.autoclicker.actions) if hasattr(self.autoclicker, 'actions') else 0
            self.action_count_label.config(text=f"动作数: {count}")
            
            disabled = sum(1 for a in self.autoclicker.actions if not a.get('enabled', True))
            self.disabled_count_label.config(text=f"禁用: {disabled}")
            
            if self.autoclicker.running and self._exec_start_time:
                elapsed = time.time() - self._exec_start_time
                self.elapsed_label.config(text=f"耗时: {elapsed:.1f}s")
            elif not self.autoclicker.running and self._exec_elapsed > 0:
                self.elapsed_label.config(text=f"耗时: {self._exec_elapsed:.1f}s")
            else:
                self.elapsed_label.config(text="耗时: --")
            
            undo_count = len(self._undo_stack) if hasattr(self, '_undo_stack') else 0
            redo_count = len(self._redo_stack) if hasattr(self, '_redo_stack') else 0
            self.undo_label.config(text=f"撤销: {undo_count} | 重做: {redo_count}")
            
            if hasattr(self.autoclicker, 'running') and self.autoclicker.running:
                self.status_indicator.config(text=self.ICON_GREEN_CIRCLE + " 运行中", foreground=self.COLOR_ACCENT)
            else:
                self.status_indicator.config(text=self.ICON_RED_CIRCLE + " 就绪", foreground=self.COLOR_DANGER)
        except Exception:
            pass
        self.window.after(100, self._update_status_bar)
    
    def _start_mouse_tracking(self):
        self._mouse_tracking = True
        self._refresh_mouse_pos()
    
    def _refresh_mouse_pos(self):
        try:
            pos = pyautogui.position()
            self.mouse_x = pos.x
            self.mouse_y = pos.y
        except Exception:
            pass
    
    def _track_mouse(self):
        if self._mouse_tracking:
            self._refresh_mouse_pos()
    
    def _toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.theme_btn_text.set(self.ICON_MOON + " 暗色")
            self._apply_dark_theme_animated()
        else:
            self.theme_btn_text.set(self.ICON_SUN_VS16 + " 亮色")
            self._apply_light_theme_animated()
    
    def _apply_dark_theme(self):
        self.window.configure(bg=self.DARK_COLOR_BG)
        nav_frame = self.window.grid_slaves(row=0, column=0)
        if nav_frame:
            nav_frame[0].configure(bg=self.DARK_COLOR_CARD)
        for i, (btn, indicator) in enumerate(zip(self.nav_buttons, self.nav_indicators)):
            if i == self.current_tab:
                btn.configure(background=self.DARK_COLOR_CARD_ALT, foreground=self.COLOR_PRIMARY)
                indicator.configure(bg=self.COLOR_PRIMARY)
            else:
                btn.configure(background=self.DARK_COLOR_BG, foreground=self.COLOR_BORDER)
                indicator.configure(bg=self.DARK_COLOR_BG)
        style = ttk.Style()
        style.configure("Treeview", background=self.DARK_COLOR_CARD, foreground=self.COLOR_BORDER,
                       fieldbackground=self.DARK_COLOR_CARD)
        style.configure("Treeview.Heading", background=self.DARK_COLOR_CARD_ALT, foreground=self.COLOR_BORDER)
        style.map("Treeview", background=[('selected', self.DARK_COLOR_TREE_SELECT)])

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb):
        return '#{:02X}{:02X}{:02X}'.format(*rgb)

    def _interpolate_color(self, color1, color2, progress):
        if isinstance(color1, str):
            c1 = self._hex_to_rgb(color1)
        else:
            c1 = color1
        if isinstance(color2, str):
            c2 = self._hex_to_rgb(color2)
        else:
            c2 = color2
        result = tuple(int(c1[i] + (c2[i] - c1[i]) * progress) for i in range(3))
        return self._rgb_to_hex(result)

    def _apply_dark_theme_animated(self):
        light_bg = self.COLOR_BG
        dark_bg = self.DARK_COLOR_BG
        light_card = self.COLOR_CARD
        dark_card = self.DARK_COLOR_CARD

        steps = self.HOVER_STEPS
        delay = self.ANIM_NORMAL // steps

        def do_apply(step=0):
            if step >= steps:
                self._apply_dark_theme()
                return
            progress = (step + 1) / steps
            interp_bg = self._interpolate_color(light_bg, dark_bg, progress)
            interp_card = self._interpolate_color(light_card, dark_card, progress)
            try:
                self.window.configure(bg=interp_bg)
                nav_frame = self.window.grid_slaves(row=0, column=0)
                if nav_frame:
                    nav_frame[0].configure(bg=interp_card)
            except Exception:
                pass
            self.window.after(delay, do_apply, step + 1)

        do_apply(0)

    def _apply_light_theme_animated(self):
        dark_bg = self.DARK_COLOR_BG
        light_bg = self.COLOR_BG
        dark_card = self.DARK_COLOR_CARD
        light_card = self.COLOR_CARD

        steps = self.HOVER_STEPS
        delay = self.ANIM_NORMAL // steps

        def do_apply(step=0):
            if step >= steps:
                self._apply_light_theme()
                return
            progress = (step + 1) / steps
            interp_bg = self._interpolate_color(dark_bg, light_bg, progress)
            interp_card = self._interpolate_color(dark_card, light_card, progress)
            try:
                self.window.configure(bg=interp_bg)
                nav_frame = self.window.grid_slaves(row=0, column=0)
                if nav_frame:
                    nav_frame[0].configure(bg=interp_card)
            except Exception:
                pass
            self.window.after(delay, do_apply, step + 1)

        do_apply(0)

    def _apply_light_theme(self):
        self.window.configure(bg=self.COLOR_BG)
        nav_frame = self.window.grid_slaves(row=0, column=0)
        if nav_frame:
            nav_frame[0].configure(bg=self.COLOR_BG)
        for i, (btn, indicator) in enumerate(zip(self.nav_buttons, self.nav_indicators)):
            if i == self.current_tab:
                btn.configure(background=self.COLOR_PRIMARY_LIGHT, foreground=self.COLOR_PRIMARY)
                indicator.configure(bg=self.COLOR_PRIMARY)
            else:
                btn.configure(background=self.COLOR_BG, foreground=self.COLOR_TEXT)
                indicator.configure(bg=self.COLOR_BG)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background=self.COLOR_CARD, foreground=self.COLOR_TEXT,
                       fieldbackground=self.COLOR_CARD)
        style.map("Treeview", background=[('selected', self.COLOR_PRIMARY)])
    
    def _on_tree_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or col_id != "#3":
            return
        
        values = self.tree.item(row_id, "values")
        if len(values) < 3:
            return
        current_val = values[2]
        
        entry = ttk.Entry(self.tree, width=30)
        entry.insert(0, current_val)
        entry.select_range(0, 'end')
        
        x, y, width, height = self.tree.bbox(row_id, col_id)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        
        def _confirm_edit():
            new_val = entry.get()
            vals = list(self.tree.item(row_id, "values"))
            vals[2] = new_val
            self.tree.item(row_id, values=vals)
            entry.destroy()
            idx = int(vals[0]) - 1
            if 0 <= idx < len(self.autoclicker.actions):
                self._push_history("编辑动作参数")
                self.autoclicker.actions[idx]['kwargs'] = self._parse_params_str(new_val)
                self.update_action_list()
        
        entry.bind("<Return>", lambda e: _confirm_edit())
        entry.bind("<FocusOut>", lambda e: entry.destroy())
        self._edit_entry = entry

    def _parse_params_str(self, params_str):
        result = {}
        try:
            for token in shlex.split(params_str):
                if '=' in token:
                    key, value = token.split('=', 1)
                    result[key.strip()] = self._parse_param_value(value)
        except Exception:
            pass
        return result

    @staticmethod
    def _parse_param_value(value):
        v = value.strip()
        if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
            return v[1:-1]
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v
    

    def _update_status_bar_count(self):
        try:
            count = len(self.autoclicker.actions) if hasattr(self.autoclicker, "actions") else 0
            self.action_count_label.config(text=f"动作数: {count}")
        except Exception:
            pass

    def _push_history(self, description="操作"):
        if not self._recording_history:
            return
        state = {
            'actions': copy.deepcopy(self.autoclicker.actions),
            'description': description
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
    
    def undo(self, event=None):
        if not self._undo_stack:
            self._log("没有可撤销的操作")
            return
        current = {
            'actions': copy.deepcopy(self.autoclicker.actions),
            'description': '撤销前状态'
        }
        self._redo_stack.append(current)
        if len(self._redo_stack) > self._max_history:
            self._redo_stack.pop(0)
        state = self._undo_stack.pop()
        self._recording_history = False
        self.autoclicker.actions = state['actions']
        self.update_action_list()
        self._recording_history = True
        self._log(f"已撤销: {state['description']}")
    
    def redo(self, event=None):
        if not self._redo_stack:
            self._log("没有可重做的操作")
            return
        current = {
            'actions': copy.deepcopy(self.autoclicker.actions),
            'description': '重做前状态'
        }
        self._undo_stack.append(current)
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        state = self._redo_stack.pop()
        self._recording_history = False
        self.autoclicker.actions = state['actions']
        self.update_action_list()
        self._recording_history = True
        self._log("已重做")

    def _highlight_action(self, index):
        if not self.highlight_progress_var.get():
            return

        def _do_highlight():
            try:
                children = self.tree.get_children()
                if 0 <= index < len(children):
                    for child in children:
                        self.tree.item(child, tags=())
                    self.tree.item(children[index], tags=('highlight',))
                    self.tree.see(children[index])
            except Exception:
                pass

        self.window.after(0, _do_highlight)

    def quit_application(self):
        self.stop_hotkey_listener()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass
        self.autoclicker.stop()
        self.window.quit()
        self.window.destroy()
    
    def run(self):
        self.window.mainloop()

def check_dependencies():
    missing = []
    
    try:
        import pyautogui
    except ImportError:
        missing.append("pyautogui")
    
    try:
        from pynput import mouse, keyboard
    except ImportError:
        missing.append("pynput")
    
    try:
        import pystray
        from PIL import Image
    except ImportError:
        pass
    
    if missing:
        response = messagebox.askyesno("依赖库缺失", 
            f"缺少以下核心依赖库：{', '.join(missing)}\n\n"
            "是否立即安装？\n\n"
            "注意：需要管理员权限。")
        
        if response:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", *missing,
                     "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                    shell=False, check=True)
                return True
            except Exception as e:
                messagebox.showerror("安装失败", "请手动安装依赖库。")
                return False
    
    return True

def main():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        if not check_dependencies():
            return
        
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.01
        
        app = AutoClickerGUI()
        app.run()
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")

if __name__ == "__main__":
    main()