"""鼠标键盘自动化脚本"""
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

# 尝试导入pynput库
PYNPUT_AVAILABLE = False
try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Listener as MouseListener
    from pynput.keyboard import Key, Listener as KeyboardListener
    PYNPUT_AVAILABLE = True
    print("√ pynput库加载成功")
except ImportError as e:
    print(f"× pynput库未安装: {e}")
    PYNPUT_AVAILABLE = False

# 系统托盘支持
PYSTRAY_AVAILABLE = False
try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
    print("√ 系统托盘模块加载成功")
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("× 系统托盘模块未安装")

class AutoClicker:
    def __init__(self):
        self.running = False
        self.actions = []
        self.current_action_index = 0
        
        # 初始化pynput控制器
        if PYNPUT_AVAILABLE:
            self.mouse_controller = mouse.Controller()
            self.keyboard_controller = keyboard.Controller()
        else:
            self.mouse_controller = None
            self.keyboard_controller = None
    
    def move_mouse(self, x, y, duration=0.5):
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            print(f"移动鼠标出错: {e}")
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
    
    def scroll(self, clicks):
        try:
            pyautogui.scroll(clicks)
            return True
        except Exception as e:
            print(f"滚动出错: {e}")
            return False
    
    def press_key(self, key, presses=1, interval=0.1):
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库处理按键
                if isinstance(key, str):
                    # 处理特殊按键
                    if key.lower() == 'space':
                        key = Key.space
                    elif key.lower() == 'enter':
                        key = Key.enter
                    elif key.lower() == 'tab':
                        key = Key.tab
                    elif key.lower() == 'esc':
                        key = Key.esc
                    elif key.lower() == 'backspace':
                        key = Key.backspace
                    elif key.lower() == 'delete':
                        key = Key.delete
                    elif key.lower() == 'shift':
                        key = Key.shift
                    elif key.lower() == 'ctrl':
                        key = Key.ctrl
                    elif key.lower() == 'alt':
                        key = Key.alt
                    elif key.lower() == 'caps_lock':
                        key = Key.caps_lock
                    elif key.lower() == 'cmd':
                        key = Key.cmd
                    elif key.lower() == 'home':
                        key = Key.home
                    elif key.lower() == 'end':
                        key = Key.end
                    elif key.lower() == 'page_up':
                        key = Key.page_up
                    elif key.lower() == 'page_down':
                        key = Key.page_down
                    elif key.lower() == 'insert':
                        key = Key.insert
                    elif key.lower() == 'menu':
                        key = Key.menu
                    elif key.lower() == 'num_lock':
                        key = Key.num_lock
                    elif key.lower() == 'print_screen':
                        key = Key.print_screen
                    elif key.lower() == 'scroll_lock':
                        key = Key.scroll_lock
                    elif key.lower() == 'pause':
                        key = Key.pause
                    elif key.lower() == 'f1':
                        key = Key.f1
                    elif key.lower() == 'f2':
                        key = Key.f2
                    elif key.lower() == 'f3':
                        key = Key.f3
                    elif key.lower() == 'f4':
                        key = Key.f4
                    elif key.lower() == 'f5':
                        key = Key.f5
                    elif key.lower() == 'f6':
                        key = Key.f6
                    elif key.lower() == 'f7':
                        key = Key.f7
                    elif key.lower() == 'f8':
                        key = Key.f8
                    elif key.lower() == 'f9':
                        key = Key.f9
                    elif key.lower() == 'f10':
                        key = Key.f10
                    elif key.lower() == 'f11':
                        key = Key.f11
                    elif key.lower() == 'f12':
                        key = Key.f12
                    else:
                        # 普通字符按键
                        pass
                
                for _ in range(presses):
                    self.keyboard_controller.press(key)
                    self.keyboard_controller.release(key)
                    if interval > 0:
                        time.sleep(interval)
            else:
                # 回退到pyautogui
                pyautogui.press(key, presses=presses, interval=interval)
            return True
        except Exception as e:
            print(f"按键出错: {e}")
            return False
    
    def type_text(self, text, interval=0.1):
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库输入文本
                for char in text:
                    self.keyboard_controller.press(char)
                    self.keyboard_controller.release(char)
                    if interval > 0:
                        time.sleep(interval)
            else:
                # 回退到pyautogui
                pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            print(f"输入文本出错: {e}")
            return False
    
    def hotkey(self, *keys):
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库处理组合键
                for key in keys:
                    if isinstance(key, str):
                        # 处理特殊按键
                        if key.lower() == 'space':
                            key = Key.space
                        elif key.lower() == 'enter':
                            key = Key.enter
                        elif key.lower() == 'tab':
                            key = Key.tab
                        elif key.lower() == 'esc':
                            key = Key.esc
                        elif key.lower() == 'backspace':
                            key = Key.backspace
                        elif key.lower() == 'delete':
                            key = Key.delete
                        elif key.lower() == 'shift':
                            key = Key.shift
                        elif key.lower() == 'ctrl':
                            key = Key.ctrl
                        elif key.lower() == 'alt':
                            key = Key.alt
                        elif key.lower() == 'caps_lock':
                            key = Key.caps_lock
                        elif key.lower() == 'cmd':
                            key = Key.cmd
                        elif key.lower() == 'home':
                            key = Key.home
                        elif key.lower() == 'end':
                            key = Key.end
                        elif key.lower() == 'page_up':
                            key = Key.page_up
                        elif key.lower() == 'page_down':
                            key = Key.page_down
                        elif key.lower() == 'insert':
                            key = Key.insert
                        elif key.lower() == 'menu':
                            key = Key.menu
                        elif key.lower() == 'num_lock':
                            key = Key.num_lock
                        elif key.lower() == 'print_screen':
                            key = Key.print_screen
                        elif key.lower() == 'scroll_lock':
                            key = Key.scroll_lock
                        elif key.lower() == 'pause':
                            key = Key.pause
                        elif key.lower() == 'f1':
                            key = Key.f1
                        elif key.lower() == 'f2':
                            key = Key.f2
                        elif key.lower() == 'f3':
                            key = Key.f3
                        elif key.lower() == 'f4':
                            key = Key.f4
                        elif key.lower() == 'f5':
                            key = Key.f5
                        elif key.lower() == 'f6':
                            key = Key.f6
                        elif key.lower() == 'f7':
                            key = Key.f7
                        elif key.lower() == 'f8':
                            key = Key.f8
                        elif key.lower() == 'f9':
                            key = Key.f9
                        elif key.lower() == 'f10':
                            key = Key.f10
                        elif key.lower() == 'f11':
                            key = Key.f11
                        elif key.lower() == 'f12':
                            key = Key.f12
                        else:
                            # 普通字符按键
                            pass
                    self.keyboard_controller.press(key)
                
                for key in reversed(keys):
                    if isinstance(key, str):
                        # 处理特殊按键
                        if key.lower() == 'space':
                            key = Key.space
                        elif key.lower() == 'enter':
                            key = Key.enter
                        elif key.lower() == 'tab':
                            key = Key.tab
                        elif key.lower() == 'esc':
                            key = Key.esc
                        elif key.lower() == 'backspace':
                            key = Key.backspace
                        elif key.lower() == 'delete':
                            key = Key.delete
                        elif key.lower() == 'shift':
                            key = Key.shift
                        elif key.lower() == 'ctrl':
                            key = Key.ctrl
                        elif key.lower() == 'alt':
                            key = Key.alt
                        elif key.lower() == 'caps_lock':
                            key = Key.caps_lock
                        elif key.lower() == 'cmd':
                            key = Key.cmd
                        elif key.lower() == 'home':
                            key = Key.home
                        elif key.lower() == 'end':
                            key = Key.end
                        elif key.lower() == 'page_up':
                            key = Key.page_up
                        elif key.lower() == 'page_down':
                            key = Key.page_down
                        elif key.lower() == 'insert':
                            key = Key.insert
                        elif key.lower() == 'menu':
                            key = Key.menu
                        elif key.lower() == 'num_lock':
                            key = Key.num_lock
                        elif key.lower() == 'print_screen':
                            key = Key.print_screen
                        elif key.lower() == 'scroll_lock':
                            key = Key.scroll_lock
                        elif key.lower() == 'pause':
                            key = Key.pause
                        elif key.lower() == 'f1':
                            key = Key.f1
                        elif key.lower() == 'f2':
                            key = Key.f2
                        elif key.lower() == 'f3':
                            key = Key.f3
                        elif key.lower() == 'f4':
                            key = Key.f4
                        elif key.lower() == 'f5':
                            key = Key.f5
                        elif key.lower() == 'f6':
                            key = Key.f6
                        elif key.lower() == 'f7':
                            key = Key.f7
                        elif key.lower() == 'f8':
                            key = Key.f8
                        elif key.lower() == 'f9':
                            key = Key.f9
                        elif key.lower() == 'f10':
                            key = Key.f10
                        elif key.lower() == 'f11':
                            key = Key.f11
                        elif key.lower() == 'f12':
                            key = Key.f12
                        else:
                            # 普通字符按键
                            pass
                    self.keyboard_controller.release(key)
            else:
                # 回退到pyautogui
                pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"组合键出错: {e}")
            return False
    
    def multi_key_press(self, keys, duration=1.0):
        """多按键同步按下功能"""
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库处理多按键同步
                key_objects = []
                for key in keys:
                    if isinstance(key, str):
                        # 处理特殊按键
                        if key.lower() == 'space':
                            key_obj = Key.space
                        elif key.lower() == 'enter':
                            key_obj = Key.enter
                        elif key.lower() == 'tab':
                            key_obj = Key.tab
                        elif key.lower() == 'esc':
                            key_obj = Key.esc
                        elif key.lower() == 'backspace':
                            key_obj = Key.backspace
                        elif key.lower() == 'delete':
                            key_obj = Key.delete
                        elif key.lower() == 'shift':
                            key_obj = Key.shift
                        elif key.lower() == 'ctrl':
                            key_obj = Key.ctrl
                        elif key.lower() == 'alt':
                            key_obj = Key.alt
                        elif key.lower() == 'caps_lock':
                            key_obj = Key.caps_lock
                        elif key.lower() == 'cmd':
                            key_obj = Key.cmd
                        elif key.lower() == 'home':
                            key_obj = Key.home
                        elif key.lower() == 'end':
                            key_obj = Key.end
                        elif key.lower() == 'page_up':
                            key_obj = Key.page_up
                        elif key.lower() == 'page_down':
                            key_obj = Key.page_down
                        elif key.lower() == 'insert':
                            key_obj = Key.insert
                        elif key.lower() == 'menu':
                            key_obj = Key.menu
                        elif key.lower() == 'num_lock':
                            key_obj = Key.num_lock
                        elif key.lower() == 'print_screen':
                            key_obj = Key.print_screen
                        elif key.lower() == 'scroll_lock':
                            key_obj = Key.scroll_lock
                        elif key.lower() == 'pause':
                            key_obj = Key.pause
                        elif key.lower() == 'f1':
                            key_obj = Key.f1
                        elif key.lower() == 'f2':
                            key_obj = Key.f2
                        elif key.lower() == 'f3':
                            key_obj = Key.f3
                        elif key.lower() == 'f4':
                            key_obj = Key.f4
                        elif key.lower() == 'f5':
                            key_obj = Key.f5
                        elif key.lower() == 'f6':
                            key_obj = Key.f6
                        elif key.lower() == 'f7':
                            key_obj = Key.f7
                        elif key.lower() == 'f8':
                            key_obj = Key.f8
                        elif key.lower() == 'f9':
                            key_obj = Key.f9
                        elif key.lower() == 'f10':
                            key_obj = Key.f10
                        elif key.lower() == 'f11':
                            key_obj = Key.f11
                        elif key.lower() == 'f12':
                            key_obj = Key.f12
                        else:
                            # 普通字符按键
                            key_obj = key
                    else:
                        key_obj = key
                    key_objects.append(key_obj)
                
                # 同时按下所有按键
                for key_obj in key_objects:
                    self.keyboard_controller.press(key_obj)
                
                # 保持按下状态一段时间
                time.sleep(duration)
                
                # 同时释放所有按键
                for key_obj in reversed(key_objects):
                    self.keyboard_controller.release(key_obj)
            else:
                # 使用pyautogui模拟多按键同步
                for key in keys:
                    pyautogui.keyDown(key)  # 按下所有键
                
                time.sleep(duration)  # 保持按下状态
                
                for key in reversed(keys):
                    pyautogui.keyUp(key)  # 释放所有键
            
            return True
        except Exception as e:
            print(f"多按键同步按下出错: {e}")
            return False
    
    def multi_mouse_press(self, buttons, duration=1.0):
        """多鼠标按键同步按下功能"""
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库处理多鼠标按键同步
                button_objects = []
                for button in buttons:
                    if button == 'left':
                        btn_obj = Button.left
                    elif button == 'right':
                        btn_obj = Button.right
                    elif button == 'middle':
                        btn_obj = Button.middle
                    else:
                        # 默认左键
                        btn_obj = Button.left
                    button_objects.append(btn_obj)
                
                # 同时按下所有鼠标按键
                for btn_obj in button_objects:
                    self.mouse_controller.press(btn_obj)
                
                # 保持按下状态一段时间
                time.sleep(duration)
                
                # 同时释放所有鼠标按键
                for btn_obj in reversed(button_objects):
                    self.mouse_controller.release(btn_obj)
            else:
                # 使用pyautogui模拟多鼠标按键同步
                for button in buttons:
                    pyautogui.mouseDown(button=button)
                
                time.sleep(duration)  # 保持按下状态
                
                for button in reversed(buttons):
                    pyautogui.mouseUp(button=button)
            
            return True
        except Exception as e:
            print(f"多鼠标按键同步按下出错: {e}")
            return False
    
    def multi_keyboard_mouse_press(self, keys, buttons, duration=1.0):
        """键盘与鼠标同时按的功能"""
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库处理键盘与鼠标同步
                key_objects = []
                for key in keys:
                    if isinstance(key, str):
                        # 处理特殊按键
                        if key.lower() == 'space':
                            key_obj = Key.space
                        elif key.lower() == 'enter':
                            key_obj = Key.enter
                        elif key.lower() == 'tab':
                            key_obj = Key.tab
                        elif key.lower() == 'esc':
                            key_obj = Key.esc
                        elif key.lower() == 'backspace':
                            key_obj = Key.backspace
                        elif key.lower() == 'delete':
                            key_obj = Key.delete
                        elif key.lower() == 'shift':
                            key_obj = Key.shift
                        elif key.lower() == 'ctrl':
                            key_obj = Key.ctrl
                        elif key.lower() == 'alt':
                            key_obj = Key.alt
                        elif key.lower() == 'caps_lock':
                            key_obj = Key.caps_lock
                        elif key.lower() == 'cmd':
                            key_obj = Key.cmd
                        elif key.lower() == 'home':
                            key_obj = Key.home
                        elif key.lower() == 'end':
                            key_obj = Key.end
                        elif key.lower() == 'page_up':
                            key_obj = Key.page_up
                        elif key.lower() == 'page_down':
                            key_obj = Key.page_down
                        elif key.lower() == 'insert':
                            key_obj = Key.insert
                        elif key.lower() == 'menu':
                            key_obj = Key.menu
                        elif key.lower() == 'num_lock':
                            key_obj = Key.num_lock
                        elif key.lower() == 'print_screen':
                            key_obj = Key.print_screen
                        elif key.lower() == 'scroll_lock':
                            key_obj = Key.scroll_lock
                        elif key.lower() == 'pause':
                            key_obj = Key.pause
                        elif key.lower() == 'f1':
                            key_obj = Key.f1
                        elif key.lower() == 'f2':
                            key_obj = Key.f2
                        elif key.lower() == 'f3':
                            key_obj = Key.f3
                        elif key.lower() == 'f4':
                            key_obj = Key.f4
                        elif key.lower() == 'f5':
                            key_obj = Key.f5
                        elif key.lower() == 'f6':
                            key_obj = Key.f6
                        elif key.lower() == 'f7':
                            key_obj = Key.f7
                        elif key.lower() == 'f8':
                            key_obj = Key.f8
                        elif key.lower() == 'f9':
                            key_obj = Key.f9
                        elif key.lower() == 'f10':
                            key_obj = Key.f10
                        elif key.lower() == 'f11':
                            key_obj = Key.f11
                        elif key.lower() == 'f12':
                            key_obj = Key.f12
                        else:
                            # 普通字符按键
                            key_obj = key
                    else:
                        key_obj = key
                    key_objects.append(key_obj)
                
                button_objects = []
                for button in buttons:
                    if button == 'left':
                        btn_obj = Button.left
                    elif button == 'right':
                        btn_obj = Button.right
                    elif button == 'middle':
                        btn_obj = Button.middle
                    else:
                        # 默认左键
                        btn_obj = Button.left
                    button_objects.append(btn_obj)
                
                # 同时按下所有键盘按键
                for key_obj in key_objects:
                    self.keyboard_controller.press(key_obj)
                
                # 同时按下所有鼠标按键
                for btn_obj in button_objects:
                    self.mouse_controller.press(btn_obj)
                
                # 保持按下状态一段时间
                time.sleep(duration)
                
                # 同时释放所有鼠标按键
                for btn_obj in reversed(button_objects):
                    self.mouse_controller.release(btn_obj)
                
                # 同时释放所有键盘按键
                for key_obj in reversed(key_objects):
                    self.keyboard_controller.release(key_obj)
            else:
                # 使用pyautogui模拟键盘与鼠标同步
                # 同时按下所有键盘按键
                for key in keys:
                    pyautogui.keyDown(key)
                
                # 同时按下所有鼠标按键
                for button in buttons:
                    pyautogui.mouseDown(button=button)
                
                # 保持按下状态一段时间
                time.sleep(duration)
                
                # 同时释放所有鼠标按键
                for button in reversed(buttons):
                    pyautogui.mouseUp(button=button)
                
                # 同时释放所有键盘按键
                for key in reversed(keys):
                    pyautogui.keyUp(key)
            
            return True
        except Exception as e:
            print(f"键盘与鼠标同时按下出错: {e}")
            return False
    
    def drag_mouse(self, x, y, duration=0.5, button='left'):
        try:
            pyautogui.dragTo(x, y, duration=duration, button=button)
            return True
        except Exception as e:
            print(f"拖拽出错: {e}")
            return False
    
    def wait(self, seconds):
        time.sleep(seconds)
        return True
    
    def get_current_position(self):
        return pyautogui.position()
    
    def get_screen_size(self):
        return pyautogui.size()
    
    def hold_mouse(self, button='left', duration=1.0):
        """长按鼠标功能"""
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库实现长按
                btn = Button.left if button == 'left' else Button.right
                self.mouse_controller.press(btn)
                time.sleep(duration)
                self.mouse_controller.release(btn)
            else:
                # 使用pyautogui模拟长按（按下后等待，然后释放）
                pyautogui.mouseDown(button=button)
                time.sleep(duration)
                pyautogui.mouseUp(button=button)
            return True
        except Exception as e:
            print(f"长按鼠标出错: {e}")
            return False
    
    def hold_key(self, key, duration=1.0):
        """长按键盘按键功能"""
        try:
            if PYNPUT_AVAILABLE:
                # 使用pynput库处理按键
                if isinstance(key, str):
                    # 处理特殊按键
                    if key.lower() == 'space':
                        key = Key.space
                    elif key.lower() == 'enter':
                        key = Key.enter
                    elif key.lower() == 'tab':
                        key = Key.tab
                    elif key.lower() == 'esc':
                        key = Key.esc
                    elif key.lower() == 'backspace':
                        key = Key.backspace
                    elif key.lower() == 'delete':
                        key = Key.delete
                    elif key.lower() == 'shift':
                        key = Key.shift
                    elif key.lower() == 'ctrl':
                        key = Key.ctrl
                    elif key.lower() == 'alt':
                        key = Key.alt
                    elif key.lower() == 'caps_lock':
                        key = Key.caps_lock
                    elif key.lower() == 'cmd':
                        key = Key.cmd
                    elif key.lower() == 'home':
                        key = Key.home
                    elif key.lower() == 'end':
                        key = Key.end
                    elif key.lower() == 'page_up':
                        key = Key.page_up
                    elif key.lower() == 'page_down':
                        key = Key.page_down
                    elif key.lower() == 'insert':
                        key = Key.insert
                    elif key.lower() == 'menu':
                        key = Key.menu
                    elif key.lower() == 'num_lock':
                        key = Key.num_lock
                    elif key.lower() == 'print_screen':
                        key = Key.print_screen
                    elif key.lower() == 'scroll_lock':
                        key = Key.scroll_lock
                    elif key.lower() == 'pause':
                        key = Key.pause
                    elif key.lower() == 'f1':
                        key = Key.f1
                    elif key.lower() == 'f2':
                        key = Key.f2
                    elif key.lower() == 'f3':
                        key = Key.f3
                    elif key.lower() == 'f4':
                        key = Key.f4
                    elif key.lower() == 'f5':
                        key = Key.f5
                    elif key.lower() == 'f6':
                        key = Key.f6
                    elif key.lower() == 'f7':
                        key = Key.f7
                    elif key.lower() == 'f8':
                        key = Key.f8
                    elif key.lower() == 'f9':
                        key = Key.f9
                    elif key.lower() == 'f10':
                        key = Key.f10
                    elif key.lower() == 'f11':
                        key = Key.f11
                    elif key.lower() == 'f12':
                        key = Key.f12
                    else:
                        # 普通字符按键
                        pass
                
                # 按下按键
                self.keyboard_controller.press(key)
                # 等待指定时间
                time.sleep(duration)
                # 释放按键
                self.keyboard_controller.release(key)
            else:
                # 使用pyautogui模拟长按（按下后等待，然后释放）
                pyautogui.keyDown(key)
                time.sleep(duration)
                pyautogui.keyUp(key)
            return True
        except Exception as e:
            print(f"长按键盘按键出错: {e}")
            return False
    
    def add_action(self, action_type, **kwargs):
        action = {
            'type': action_type,
            'kwargs': kwargs,
            'timestamp': time.time()
        }
        self.actions.append(action)
        return action
    
    def insert_action_at(self, index, action_type, **kwargs):
        """在指定位置插入动作"""
        action = {
            'type': action_type,
            'kwargs': kwargs,
            'timestamp': time.time()
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
                self.actions = json.load(f)
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
                f.write("# 支持的动作类型: move, click, double_click, right_click, left_click, scroll, press, type, hotkey, drag, wait, hold, key_hold, multi_key, multi_mouse, multi_key_mouse\n")
                f.write("\n")
                
                for i, action in enumerate(self.actions):
                    action_type = action['type']
                    kwargs = action['kwargs']
                    
                    line = f"{action_type}"
                    for key, value in kwargs.items():
                        if isinstance(value, str):
                            line += f" {key}='{value}'"
                        else:
                            line += f" {key}={value}"
                    f.write(line + "\n")
            return True
        except Exception as e:
            print(f"保存为文本文件出错: {e}")
            return False
    
    def load_from_txt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            actions = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if not parts:
                    continue
                
                action_type = parts[0]
                kwargs = {}
                
                for part in parts[1:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        if value.startswith("'") and value.endswith("'"):
                            kwargs[key] = value[1:-1]
                        else:
                            try:
                                kwargs[key] = int(value)
                            except ValueError:
                                try:
                                    kwargs[key] = float(value)
                                except ValueError:
                                    kwargs[key] = value
                
                action = {
                    'type': action_type,
                    'kwargs': kwargs,
                    'timestamp': time.time()
                }
                actions.append(action)
            
            self.actions = actions
            return True
        except Exception as e:
            print(f"从文本文件加载出错: {e}")
            return False
    
    def run_actions(self, repeat=1, interval=0):
        self.running = True
        self.current_action_index = 0
        
        for repeat_count in range(repeat):
            if not self.running:
                break
                
            for i, action in enumerate(self.actions):
                if not self.running:
                    break
                    
                self.current_action_index = i
                action_type = action['type']
                kwargs = action['kwargs']
                
                if action_type == 'move':
                    self.move_mouse(**kwargs)
                elif action_type == 'click':
                    self.click_mouse(**kwargs)
                elif action_type == 'double_click':
                    self.double_click(**kwargs)
                elif action_type == 'right_click':
                    self.right_click(**kwargs)
                elif action_type == 'left_click':
                    self.left_click(**kwargs)
                elif action_type == 'scroll':
                    self.scroll(**kwargs)
                elif action_type == 'press':
                    self.press_key(**kwargs)
                elif action_type == 'type':
                    self.type_text(**kwargs)
                elif action_type == 'hotkey':
                    self.hotkey(**kwargs)
                elif action_type == 'drag':
                    self.drag_mouse(**kwargs)
                elif action_type == 'wait':
                    self.wait(**kwargs)
                elif action_type == 'hold':
                    self.hold_mouse(**kwargs)
                elif action_type == 'key_hold':
                    self.hold_key(**kwargs)
                elif action_type == 'multi_key':
                    self.multi_key_press(**kwargs)
                elif action_type == 'multi_mouse':
                    self.multi_mouse_press(**kwargs)
                elif action_type == 'multi_key_mouse':
                    self.multi_keyboard_mouse_press(**kwargs)
                
                if interval > 0 and i < len(self.actions) - 1:
                    time.sleep(interval)
            
            if repeat_count < repeat - 1 and interval > 0:
                time.sleep(interval)
        
        self.running = False
    
    def stop(self):
        self.running = False

class AutoClickerGUI:
    def __init__(self):
        self.autoclicker = AutoClicker()
        self.window = tk.Tk()
        self.window.title("鼠标键盘自动化控制 v6.0 - 精简版")
        self.window.geometry("900x850")
        
        # 位置缓存，用于存储F2记录的位置
        self.position_cache = []
        
        # 系统托盘变量
        self.tray_icon = None
        self.is_hidden = False
        
        # 热键监听器
        self.listener = None
        self.hotkey_active = False
        
        # 设置窗口关闭行为
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        # 创建UI
        self.setup_ui()
        
        # 检查管理员权限
        self.check_admin_privileges()
        
        # 设置安全功能
        self.toggle_safety()
        
        # 启动全局热键监听
        self.start_hotkey_listener()
    
    def check_admin_privileges(self):
        """检查是否以管理员身份运行"""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("警告: 未以管理员身份运行，某些功能可能受限")
                print("建议: 右键点击程序 -> '以管理员身份运行'")
                return False
            else:
                print("✓ 程序以管理员身份运行")
                return True
        except:
            print("无法检测管理员权限")
            return False
    
    def setup_ui(self):
        """创建UI界面"""
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 移除手动控制选项卡
        # self.create_manual_tab(notebook)
        
        self.create_sequence_tab(notebook)
        self.create_settings_tab(notebook)
        
        # 创建托盘图标（如果可用）
        if PYSTRAY_AVAILABLE:
            self.create_tray_icon()
    
    def create_tray_icon(self):
        """创建系统托盘图标"""
        try:
            # 创建简单的图标
            image = Image.new('RGB', (64, 64), color='white')
            dc = ImageDraw.Draw(image)
            dc.rectangle([16, 16, 48, 48], fill='blue')
            
            # 创建托盘菜单
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
    
    def start_hotkey_listener(self):
        """启动全局热键监听"""
        try:
            if PYNPUT_AVAILABLE:
                # 定义热键回调函数
                def on_press(key):
                    try:
                        # 检测F1键用于开始/停止
                        if key == Key.f1:
                            if self.autoclicker.running:
                                self.stop_sequence()
                            else:
                                self.start_sequence()
                        # 检测F2键用于获取鼠标位置
                        elif key == Key.f2:
                            pos = self.autoclicker.get_current_position()
                            # 在主线程中安全地调用 messagebox
                            self.window.after(0, lambda: self.record_position(pos))
                    except Exception as e:
                        print(f"热键处理出错: {e}")
                
                # 启动键盘监听器
                self.listener = keyboard.Listener(on_press=on_press)
                self.listener.start()
                self.hotkey_active = True
                print("✓ 全局热键监听已启动 (F1: 开始/停止, F2: 获取并记录鼠标位置)")
            else:
                print("× pynput库不可用，无法启动全局热键")
        except Exception as e:
            print(f"启动热键监听失败: {e}")
    
    def record_position(self, pos):
        """记录F2获取的位置"""
        # 限制缓存最多存储10个位置
        if len(self.position_cache) >= 10:
            # 移除最早的一个位置
            self.position_cache.pop(0)
        
        # 添加新位置
        position_info = {"x": pos.x, "y": pos.y, "time": time.strftime('%H:%M:%S')}
        self.position_cache.append(position_info)
        
        # 弹窗显示位置信息
        messagebox.showinfo("F2位置记录", f"已记录鼠标位置: X={pos.x}, Y={pos.y}\n总记录位置数: {len(self.position_cache)}")
    
    def stop_hotkey_listener(self):
        """停止全局热键监听"""
        try:
            if self.listener:
                self.listener.stop()
                self.hotkey_active = False
                print("全局热键监听已停止")
        except Exception as e:
            print(f"停止热键监听失败: {e}")
    
    def create_sequence_tab(self, notebook):
        """创建动作序列选项卡"""
        seq_frame = ttk.Frame(notebook)
        notebook.add(seq_frame, text="动作序列")
        
        # 动作列表
        list_frame = ttk.LabelFrame(seq_frame, text="动作列表", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 创建树形视图显示动作
        columns = ('序号', '类型', '参数', '时间')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 右键菜单
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="在上方插入移动指令", command=self.insert_move_above)
        self.context_menu.add_command(label="在上方插入左键点击", command=lambda: self.insert_click_above('left'))
        self.context_menu.add_command(label="在上方插入右键点击", command=lambda: self.insert_click_above('right'))
        self.context_menu.add_command(label="在上方插入等待指令", command=self.insert_wait_above)
        self.context_menu.add_command(label="在上方插入按键指令", command=self.insert_key_above)
        self.context_menu.add_command(label="在上方插入拖拽指令", command=self.insert_drag_above)
        self.context_menu.add_command(label="在上方插入滚动指令", command=self.insert_scroll_above)
        self.context_menu.add_command(label="在上方插入长按指令", command=self.insert_hold_above)
        self.context_menu.add_command(label="在上方插入键盘长按指令", command=self.insert_key_hold_above)
        self.context_menu.add_command(label="在上方插入多按键同步指令", command=self.insert_multi_key_above)
        self.context_menu.add_command(label="在上方插入多鼠标按键同步指令", command=self.insert_multi_mouse_above)
        self.context_menu.add_command(label="在上方插入键盘与鼠标同步指令", command=self.insert_multi_key_mouse_above)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除选中", command=self.delete_selected_action)
        
        # 绑定右键菜单事件
        self.tree.bind("<Button-3>", self.show_context_menu)
        
        # 动作控制按钮
        control_frame = ttk.Frame(seq_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        # 创建可滚动的按钮区域
        canvas_frame = ttk.Frame(control_frame)
        canvas_frame.pack(fill='x', expand=True)
        
        canvas = tk.Canvas(canvas_frame, height=80)
        scrollbar_h = ttk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar_h.set)
        
        # 添加按钮到滚动框架
        self.add_buttons_to_frame(scrollable_frame)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar_h.pack(side="bottom", fill="x")
        
        # 执行控制
        execute_frame = ttk.LabelFrame(seq_frame, text="执行控制", padding=10)
        execute_frame.pack(fill='x', padx=10, pady=5)
        
        exec_control_frame = ttk.Frame(execute_frame)
        exec_control_frame.pack(fill='x', pady=5)
        
        ttk.Label(exec_control_frame, text="重复次数:").pack(side='left')
        self.repeat_var = tk.StringVar(value="1")
        repeat_spin = ttk.Spinbox(exec_control_frame, from_=1, to=999, 
                                 textvariable=self.repeat_var, width=5)
        repeat_spin.pack(side='left', padx=5)
        
        ttk.Label(exec_control_frame, text="动作间隔(秒):").pack(side='left', padx=10)
        self.interval_var = tk.StringVar(value="0.5")
        interval_spin = ttk.Spinbox(exec_control_frame, from_=0, to=10, 
                                   increment=0.1, textvariable=self.interval_var, width=5)
        interval_spin.pack(side='left', padx=5)
        
        ttk.Button(exec_control_frame, text="开始执行", 
                  command=self.start_sequence).pack(side='left', padx=20)
        ttk.Button(exec_control_frame, text="停止", 
                  command=self.stop_sequence).pack(side='left', padx=5)
        
        # 文件操作
        file_frame = ttk.Frame(execute_frame)
        file_frame.pack(fill='x', pady=5)
        
        ttk.Button(file_frame, text="保存序列(.json)", 
                  command=self.save_sequence).pack(side='left', padx=5)
        ttk.Button(file_frame, text="加载序列(.json)", 
                  command=self.load_sequence).pack(side='left', padx=5)
        ttk.Button(file_frame, text="保存脚本(.txt)", 
                  command=self.save_script_txt).pack(side='left', padx=5)
        ttk.Button(file_frame, text="加载脚本(.txt)", 
                  command=self.load_script_txt).pack(side='left', padx=5)
    
    def add_buttons_to_frame(self, parent_frame):
        """将所有按钮添加到指定框架"""
        # 添加一个带下拉菜单的移动按钮
        move_button_frame = ttk.Frame(parent_frame)
        move_button_frame.pack(side='left', padx=5)
        
        # 主按钮
        self.move_button = ttk.Button(move_button_frame, text="添加移动", 
                                     command=self.add_move_action)
        self.move_button.pack(side='top')
        
        # 下拉箭头按钮
        self.move_dropdown = ttk.Button(move_button_frame, text="▼", width=3,
                                       command=self.show_position_menu)
        self.move_dropdown.pack(side='bottom')
        
        ttk.Button(parent_frame, text="添加左键点击", 
                  command=lambda: self.add_click_action('left')).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加右键点击", 
                  command=lambda: self.add_click_action('right')).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加等待", 
                  command=self.add_wait_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加按键", 
                  command=self.add_key_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加拖拽", 
                  command=self.add_drag_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加滚动", 
                  command=self.add_scroll_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加长按", 
                  command=self.add_hold_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加键盘长按", 
                  command=self.add_key_hold_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加多按键同步", 
                  command=self.add_multi_key_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加多鼠标同步", 
                  command=self.add_multi_mouse_action).pack(side='left', padx=5)
        ttk.Button(parent_frame, text="添加键盘鼠标同步", 
                  command=self.add_multi_key_mouse_action).pack(side='left', padx=5)
        
        ttk.Button(parent_frame, text="删除选中", 
                  command=self.delete_selected_action).pack(side='left', padx=20)
        ttk.Button(parent_frame, text="清空列表", 
                  command=self.clear_action_list).pack(side='left', padx=5)
    
    def show_position_menu(self):
        """显示记录的位置菜单"""
        if not self.position_cache:
            messagebox.showinfo("位置记录", "暂无F2记录的位置")
            return
        
        # 创建临时菜单
        temp_menu = tk.Menu(self.window, tearoff=0)
        
        # 添加每个记录的位置
        for i, pos in enumerate(self.position_cache):
            label = f"位置{i+1}: ({pos['x']}, {pos['y']}) - {pos['time']}"
            temp_menu.add_command(
                label=label,
                command=lambda x=pos['x'], y=pos['y']: self.add_move_with_position(x, y)
            )
        
        # 添加清除记录选项
        temp_menu.add_separator()
        temp_menu.add_command(label="清除所有位置记录", command=self.clear_position_cache)
        
        # 显示菜单
        try:
            temp_menu.tk_popup(self.move_dropdown.winfo_rootx(), 
                              self.move_dropdown.winfo_rooty() + self.move_dropdown.winfo_height())
        finally:
            temp_menu.grab_release()
    
    def add_move_with_position(self, x, y):
        """使用指定位置添加移动动作"""
        action = self.autoclicker.add_action('move', x=x, y=y)
        self.update_action_list()
        messagebox.showinfo("成功", f"已添加移动到位置: X={x}, Y={y}")
    
    def clear_position_cache(self):
        """清除位置缓存"""
        if messagebox.askyesno("确认", "确定要清除所有F2记录的位置吗？"):
            self.position_cache.clear()
            messagebox.showinfo("清除成功", "位置缓存已清空")
    
    def create_settings_tab(self, notebook):
        """创建设置选项卡"""
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="设置与帮助")
        
        # 权限状态
        admin_frame = ttk.LabelFrame(settings_frame, text="权限状态", padding=10)
        admin_frame.pack(fill='x', padx=10, pady=5)
        
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if is_admin:
                status_text = "✓ 当前以管理员身份运行"
                status_color = "green"
            else:
                status_text = "⚠ 当前未以管理员身份运行"
                status_color = "orange"
        except:
            status_text = "? 无法检测管理员权限"
            status_color = "gray"
        
        admin_label = ttk.Label(admin_frame, text=status_text, foreground=status_color)
        admin_label.pack(anchor='w')
        
        # 库状态
        library_frame = ttk.LabelFrame(settings_frame, text="库状态", padding=10)
        library_frame.pack(fill='x', padx=10, pady=5)
        
        if PYNPUT_AVAILABLE:
            lib_status = "✓ pynput库已加载 - 推荐使用"
            lib_color = "green"
        else:
            lib_status = "✗ pynput库未安装 - 使用pyautogui替代"
            lib_color = "red"
        
        lib_label = ttk.Label(library_frame, text=lib_status, foreground=lib_color)
        lib_label.pack(anchor='w')
        
        # 热键状态
        hotkey_frame = ttk.LabelFrame(settings_frame, text="热键状态", padding=10)
        hotkey_frame.pack(fill='x', padx=10, pady=5)
        
        if self.hotkey_active:
            hotkey_status = "✓ 全局热键已激活 - F1: 开始/停止执行, F2: 记录鼠标位置"
            hotkey_color = "green"
        else:
            hotkey_status = "✗ 全局热键未激活"
            hotkey_color = "red"
        
        hotkey_label = ttk.Label(hotkey_frame, text=hotkey_status, foreground=hotkey_color)
        hotkey_label.pack(anchor='w')
        
        # 位置记录状态
        pos_frame = ttk.LabelFrame(settings_frame, text="位置记录状态", padding=10)
        pos_frame.pack(fill='x', padx=10, pady=5)
        
        self.pos_status_label = ttk.Label(pos_frame, text=f"已记录位置数: {len(self.position_cache)}", foreground="blue")
        self.pos_status_label.pack(anchor='w')
        
        ttk.Button(pos_frame, text="查看位置记录", command=self.view_position_cache).pack(side='left', padx=5)
        ttk.Button(pos_frame, text="清除位置记录", command=self.clear_position_cache).pack(side='left', padx=5)
        
        # 后台控制
        background_frame = ttk.LabelFrame(settings_frame, text="后台控制", padding=10)
        background_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(background_frame, text="最小化到系统托盘", 
                  command=self.minimize_to_tray).pack(side='left', padx=5)
        ttk.Button(background_frame, text="显示/隐藏窗口", 
                  command=self.toggle_window_visibility).pack(side='left', padx=5)
        
        # 热键说明
        hotkey_info_frame = ttk.LabelFrame(settings_frame, text="热键说明", padding=10)
        hotkey_info_frame.pack(fill='x', padx=10, pady=5)
        
        hotkey_text = """全局热键（即使窗口不在前台也能工作）：
        - F1: 开始/停止执行任务
        - F2: 记录当前鼠标位置到缓存
        
        重要提示：
        1. 请确保以管理员身份运行本程序
        2. 部分防病毒软件可能阻止键盘钩子
        3. 在全屏游戏中，确保游戏不是"独占全屏"模式
        """
        
        hotkey_label = ttk.Label(hotkey_info_frame, text=hotkey_text, justify='left')
        hotkey_label.pack(anchor='w')
        
        # 功能说明
        features_frame = ttk.LabelFrame(settings_frame, text="功能说明", padding=10)
        features_frame.pack(fill='x', padx=10, pady=5)
        
        features_text = """功能特性：
        1. 动作序列：录制、编辑、执行自动化任务
        2. 长按功能：支持长按鼠标按钮指定时间
        3. 键盘长按功能：支持长按键盘按键指定时间
        4. 多按键同步功能：支持同时按下多个键盘或鼠标按键
        5. 键盘与鼠标同步功能：支持键盘和鼠标按键同时按下
        6. pynput库：更精确的键盘输入输出控制
        7. 全局热键：F1/F2键可在任何地方快速操作
        8. 后台运行：可最小化到系统托盘继续执行
        9. 按键选择功能：支持特殊按键的处理
        10. 按键选择器：字母显示为小写
        11. F2位置记录：按F2可记录当前位置，通过下拉菜单快速添加到动作序列
        12. 自适应UI：当按钮过多时自动出现滚动条
        13. 键盘鼠标同步：所有按键无延迟同时按下
        """
        
        features_label = ttk.Label(features_frame, text=features_text, justify='left')
        features_label.pack(anchor='w')
        
        # 安全设置
        safety_frame = ttk.LabelFrame(settings_frame, text="安全设置", padding=10)
        safety_frame.pack(fill='x', padx=10, pady=5)
        
        self.safety_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(safety_frame, text="启用故障安全功能（移动鼠标到屏幕左上角停止程序）", 
                       variable=self.safety_var, 
                       command=self.toggle_safety).pack(anchor='w')
        
        ttk.Label(safety_frame, 
                 text="注意：启用后，将鼠标快速移动到屏幕左上角(0,0)可以紧急停止程序",
                 foreground='gray').pack(anchor='w', pady=5)
        
        # 安装提示
        install_frame = ttk.LabelFrame(settings_frame, text="依赖库安装", padding=10)
        install_frame.pack(fill='x', padx=10, pady=5)
        
        install_text = """如果pynput库未安装，请以管理员身份运行以下命令：
        
        命令提示符（管理员）：
        pip install pyautogui pystray pillow pynput
        
        或者使用清华镜像源加速：
        pip install pyautogui pystray pillow pynput -i https://pypi.tuna.tsinghua.edu.cn/simple
        """
        
        install_label = ttk.Label(install_frame, text=install_text, justify='left')
        install_label.pack(anchor='w')
    
    def view_position_cache(self):
        """查看位置缓存"""
        if not self.position_cache:
            messagebox.showinfo("位置记录", "暂无F2记录的位置")
            return
        
        # 创建显示窗口
        cache_window = tk.Toplevel(self.window)
        cache_window.title("F2记录的位置")
        cache_window.geometry("400x300")
        
        # 创建文本框显示位置信息
        text_widget = tk.Text(cache_window, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(cache_window, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # 插入位置信息
        for i, pos in enumerate(self.position_cache):
            text_widget.insert(tk.END, f"位置{i+1}: X={pos['x']}, Y={pos['y']} - 记录时间: {pos['time']}\n")
        
        text_widget.config(state=tk.DISABLED)  # 设置为只读
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        try:
            # 选择被点击的项目
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"显示右键菜单出错: {e}")
    
    def get_selected_index(self):
        """获取选中项的索引"""
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0])['values']
            index = int(item_values[0]) - 1  # 转换为0基索引
            return index
        return None
    
    def insert_move_above(self):
        """在选中项上方插入移动指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            x = simpledialog.askinteger("X坐标", "请输入X坐标:")
            y = simpledialog.askinteger("Y坐标", "请输入Y坐标:")
            if x is not None and y is not None:
                self.autoclicker.insert_action_at(index, 'move', x=x, y=y)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入移动指令")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字")
    
    def insert_click_above(self, button_type='left'):
        """在选中项上方插入点击指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        self.autoclicker.insert_action_at(index, 'click', button=button_type, clicks=1)
        self.update_action_list()
        button_name = "左键" if button_type == 'left' else "右键"
        messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入{button_name}点击指令")
    
    def insert_wait_above(self):
        """在选中项上方插入等待指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        wait_time = simpledialog.askfloat("等待时间", "请输入等待时间（秒）:", 
                                          initialvalue=1.0, minvalue=0.1, maxvalue=60)
        if wait_time:
            self.autoclicker.insert_action_at(index, 'wait', seconds=wait_time)
            self.update_action_list()
            messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入等待指令")
    
    def insert_key_above(self):
        """在选中项上方插入按键指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        # 显示按键选择对话框
        key = self.select_key_dialog("在上方插入按键")
        if key:
            self.autoclicker.insert_action_at(index, 'press', key=key)
            self.update_action_list()
            messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入按键指令: {key}")
    
    def insert_drag_above(self):
        """在选中项上方插入拖拽指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            x = simpledialog.askinteger("目标X坐标", "请输入目标X坐标:")
            y = simpledialog.askinteger("目标Y坐标", "请输入目标Y坐标:")
            if x is not None and y is not None:
                self.autoclicker.insert_action_at(index, 'drag', x=x, y=y)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入拖拽指令")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字")
    
    def insert_scroll_above(self):
        """在选中项上方插入滚动指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            scroll_amount = simpledialog.askinteger("滚动量", "请输入滚动单位数量（正数向上，负数向下）:", 
                                                    initialvalue=1, minvalue=-100, maxvalue=100)
            if scroll_amount is not None:
                self.autoclicker.insert_action_at(index, 'scroll', clicks=scroll_amount)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入滚动指令")
        except Exception as e:
            messagebox.showerror("错误", f"插入滚动指令时出错: {e}")
    
    def insert_hold_above(self):
        """在选中项上方插入长按指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            button_type = simpledialog.askstring("按钮类型", "请输入按钮类型（left/right）:", 
                                                initialvalue="left")
            if button_type not in ['left', 'right']:
                messagebox.showerror("错误", "按钮类型只能是 left 或 right")
                return
                
            duration = simpledialog.askfloat("长按时间", "请输入长按时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                self.autoclicker.insert_action_at(index, 'hold', button=button_type, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入长按指令")
        except Exception as e:
            messagebox.showerror("错误", f"插入长按指令时出错: {e}")
    
    def insert_key_hold_above(self):
        """在选中项上方插入键盘长按指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            key = self.select_key_dialog("在上方插入键盘长按")
            if not key:
                return
                
            duration = simpledialog.askfloat("长按时间", "请输入长按时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                self.autoclicker.insert_action_at(index, 'key_hold', key=key, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入键盘长按指令")
        except Exception as e:
            messagebox.showerror("错误", f"插入键盘长按指令时出错: {e}")
    
    def insert_multi_key_above(self):
        """在选中项上方插入多按键同步指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            # 提示用户输入按键列表
            keys_input = simpledialog.askstring("多按键同步", "请输入要同时按下的按键（用逗号分隔）:", 
                                               initialvalue="w,a,s,d")
            if not keys_input:
                return
                
            keys = [k.strip() for k in keys_input.split(',')]
            
            duration = simpledialog.askfloat("持续时间", "请输入按键持续时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                self.autoclicker.insert_action_at(index, 'multi_key', keys=keys, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入多按键同步指令")
        except Exception as e:
            messagebox.showerror("错误", f"插入多按键同步指令时出错: {e}")
    
    def insert_multi_mouse_above(self):
        """在选中项上方插入多鼠标按键同步指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            # 提示用户输入鼠标按键列表
            buttons_input = simpledialog.askstring("多鼠标按键同步", "请输入要同时按下的鼠标按键（left,right,middle，用逗号分隔）:", 
                                                 initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            duration = simpledialog.askfloat("持续时间", "请输入按键持续时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                self.autoclicker.insert_action_at(index, 'multi_mouse', buttons=buttons, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入多鼠标按键同步指令")
        except Exception as e:
            messagebox.showerror("错误", f"插入多鼠标按键同步指令时出错: {e}")
    
    def insert_multi_key_mouse_above(self):
        """在选中项上方插入键盘与鼠标同步指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return
            
        try:
            # 提示用户输入键盘按键列表
            keys_input = simpledialog.askstring("键盘按键", "请输入要同时按下的键盘按键（用逗号分隔）:", 
                                               initialvalue="w,a,s,d")
            if not keys_input:
                return
                
            keys = [k.strip() for k in keys_input.split(',')]
            
            # 提示用户输入鼠标按键列表
            buttons_input = simpledialog.askstring("鼠标按键", "请输入要同时按下的鼠标按键（left,right,middle，用逗号分隔）:", 
                                                 initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            duration = simpledialog.askfloat("持续时间", "请输入按键持续时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                self.autoclicker.insert_action_at(index, 'multi_key_mouse', keys=keys, buttons=buttons, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入键盘与鼠标同步指令")
        except Exception as e:
            messagebox.showerror("错误", f"插入键盘与鼠标同步指令时出错: {e}")
    
    def select_key_dialog(self, title="选择按键"):
        """弹出按键选择对话框"""
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.geometry("400x300")
        dialog.transient(self.window)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.window.winfo_rootx()+50, self.window.winfo_rooty()+50))
        
        categories = {
            "字母": [chr(i) for i in range(ord('a'), ord('z')+1)],
            "数字": [str(i) for i in range(0, 10)],
            "功能键": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            "控制键": ["space", "enter", "tab", "esc", "backspace", "delete", "shift", "ctrl", "alt", "caps_lock", "cmd"],
            "导航键": ["home", "end", "page_up", "page_down", "insert", "menu", "up", "down", "left", "right"],
            "其他": ["print_screen", "scroll_lock", "pause", "num_lock"]
        }
        
        selected_key = tk.StringVar()
        
        # 创建标签页
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        for category, keys in categories.items():
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=category)
            
            # 计算每行按钮数量
            buttons_per_row = 6
            row, col = 0, 0
            
            for key in keys:
                btn = ttk.Button(frame, text=key, width=10, 
                               command=lambda k=key: [selected_key.set(k), dialog.destroy()])
                btn.grid(row=row, column=col, padx=2, pady=2)
                
                col += 1
                if col >= buttons_per_row:
                    col = 0
                    row += 1
        
        # 添加自定义输入框
        custom_frame = ttk.Frame(dialog)
        custom_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(custom_frame, text="或输入自定义按键:").pack(side='left')
        custom_entry = ttk.Entry(custom_frame, width=15)
        custom_entry.pack(side='left', padx=5)
        
        def use_custom_key():
            custom_value = custom_entry.get().strip()
            if custom_value:
                selected_key.set(custom_value)
                dialog.destroy()
        
        ttk.Button(custom_frame, text="使用自定义", command=use_custom_key).pack(side='left', padx=5)
        
        # 等待对话框关闭
        self.window.wait_window(dialog)
        
        return selected_key.get()
    
    def get_current_pos(self):
        pos = self.autoclicker.get_current_position()
        # 不再设置到输入框，直接弹窗
        messagebox.showinfo("当前位置", f"当前鼠标位置: X={pos.x}, Y={pos.y}")
    
    def move_to_pos(self):
        # 此函数已无用，因为移除了手动控制界面
        pass
    
    def type_text(self):
        # 此函数已无用，因为移除了手动控制界面
        pass
    
    def add_move_action(self):
        try:
            x = simpledialog.askinteger("X坐标", "请输入X坐标:")
            y = simpledialog.askinteger("Y坐标", "请输入Y坐标:")
            if x is not None and y is not None:
                action = self.autoclicker.add_action('move', x=x, y=y)
                self.update_action_list()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字")
    
    def add_click_action(self, button_type='left'):
        """添加点击动作"""
        action = self.autoclicker.add_action('click', button=button_type, clicks=1)
        self.update_action_list()
        button_name = "左键" if button_type == 'left' else "右键"
        messagebox.showinfo("成功", f"已添加{button_name}点击动作")
    
    def add_wait_action(self):
        wait_time = simpledialog.askfloat("等待时间", "请输入等待时间（秒）:", 
                                          initialvalue=1.0, minvalue=0.1, maxvalue=60)
        if wait_time:
            action = self.autoclicker.add_action('wait', seconds=wait_time)
            self.update_action_list()
    
    def add_key_action(self):
        key = self.select_key_dialog("添加按键")
        if key:
            action = self.autoclicker.add_action('press', key=key)
            self.update_action_list()
            messagebox.showinfo("成功", f"已添加按键动作: {key}")
    
    def add_drag_action(self):
        try:
            x = simpledialog.askinteger("目标X坐标", "请输入目标X坐标:")
            y = simpledialog.askinteger("目标Y坐标", "请输入目标Y坐标:")
            if x is not None and y is not None:
                action = self.autoclicker.add_action('drag', x=x, y=y)
                self.update_action_list()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字")
    
    def add_scroll_action(self):
        """添加滚动动作"""
        try:
            scroll_amount = simpledialog.askinteger("滚动量", "请输入滚动单位数量（正数向上，负数向下）:", 
                                                    initialvalue=1, minvalue=-100, maxvalue=100)
            if scroll_amount is not None:
                action = self.autoclicker.add_action('scroll', clicks=scroll_amount)
                self.update_action_list()
                messagebox.showinfo("成功", f"已添加滚动 {scroll_amount} 单位")
        except Exception as e:
            messagebox.showerror("错误", f"添加滚动动作时出错: {e}")
    
    def add_hold_action(self):
        """添加长按动作"""
        try:
            button_type = simpledialog.askstring("按钮类型", "请输入按钮类型（left/right）:", 
                                                initialvalue="left")
            if button_type not in ['left', 'right']:
                messagebox.showerror("错误", "按钮类型只能是 left 或 right")
                return
                
            duration = simpledialog.askfloat("长按时间", "请输入长按时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                action = self.autoclicker.add_action('hold', button=button_type, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已添加长按 {button_type} 键 {duration} 秒")
        except Exception as e:
            messagebox.showerror("错误", f"添加长按动作时出错: {e}")
    
    def add_key_hold_action(self):
        """添加键盘长按动作"""
        try:
            key = self.select_key_dialog("添加键盘长按")
            if not key:
                return
                
            duration = simpledialog.askfloat("长按时间", "请输入长按时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                action = self.autoclicker.add_action('key_hold', key=key, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已添加键盘长按 {key} 键 {duration} 秒")
        except Exception as e:
            messagebox.showerror("错误", f"添加键盘长按动作时出错: {e}")
    
    def add_multi_key_action(self):
        """添加多按键同步动作"""
        try:
            # 提示用户输入按键列表
            keys_input = simpledialog.askstring("多按键同步", "请输入要同时按下的按键（用逗号分隔）:", 
                                               initialvalue="w,a,s,d")
            if not keys_input:
                return
                
            keys = [k.strip() for k in keys_input.split(',')]
            
            duration = simpledialog.askfloat("持续时间", "请输入按键持续时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                action = self.autoclicker.add_action('multi_key', keys=keys, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已添加多按键同步动作: {keys} 持续 {duration} 秒")
        except Exception as e:
            messagebox.showerror("错误", f"添加多按键同步动作时出错: {e}")
    
    def add_multi_mouse_action(self):
        """添加多鼠标按键同步动作"""
        try:
            # 提示用户输入鼠标按键列表
            buttons_input = simpledialog.askstring("多鼠标按键同步", "请输入要同时按下的鼠标按键（left,right,middle，用逗号分隔）:", 
                                                 initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            duration = simpledialog.askfloat("持续时间", "请输入按键持续时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                action = self.autoclicker.add_action('multi_mouse', buttons=buttons, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已添加多鼠标按键同步动作: {buttons} 持续 {duration} 秒")
        except Exception as e:
            messagebox.showerror("错误", f"添加多鼠标按键同步动作时出错: {e}")
    
    def add_multi_key_mouse_action(self):
        """添加键盘与鼠标同步动作"""
        try:
            # 提示用户输入键盘按键列表
            keys_input = simpledialog.askstring("键盘按键", "请输入要同时按下的键盘按键（用逗号分隔）:", 
                                               initialvalue="w,a,s,d")
            if not keys_input:
                return
                
            keys = [k.strip() for k in keys_input.split(',')]
            
            # 提示用户输入鼠标按键列表
            buttons_input = simpledialog.askstring("鼠标按键", "请输入要同时按下的鼠标按键（left,right,middle，用逗号分隔）:", 
                                                 initialvalue="left,right")
            if not buttons_input:
                return
                
            buttons = [b.strip() for b in buttons_input.split(',')]
            
            duration = simpledialog.askfloat("持续时间", "请输入按键持续时间（秒）:", 
                                           initialvalue=1.0, minvalue=0.1, maxvalue=10)
            if duration:
                action = self.autoclicker.add_action('multi_key_mouse', keys=keys, buttons=buttons, duration=duration)
                self.update_action_list()
                messagebox.showinfo("成功", f"已添加键盘与鼠标同步动作: 键盘{keys} + 鼠标{buttons} 持续 {duration} 秒")
        except Exception as e:
            messagebox.showerror("错误", f"添加键盘与鼠标同步动作时出错: {e}")
    
    def delete_selected_action(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要删除的动作")
            return
        
        for item in selected:
            index = int(self.tree.item(item)['values'][0]) - 1
            if 0 <= index < len(self.autoclicker.actions):
                del self.autoclicker.actions[index]
        
        self.update_action_list()
    
    def clear_action_list(self):
        if messagebox.askyesno("确认", "确定要清空所有动作吗？"):
            self.autoclicker.clear_actions()
            self.update_action_list()
    
    def update_action_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for i, action in enumerate(self.autoclicker.actions):
            action_type = action['type']
            kwargs = action['kwargs']
            params_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
            timestamp = time.strftime('%H:%M:%S', time.localtime(action['timestamp']))
            
            self.tree.insert('', 'end', values=(i+1, action_type, params_str, timestamp))
    
    def start_sequence(self):
        try:
            repeat = int(self.repeat_var.get())
            interval = float(self.interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "请检查重复次数和间隔时间的数值")
            return
        
        def run_in_thread():
            self.autoclicker.run_actions(repeat=repeat, interval=interval)
        
        thread = threading.Thread(target=run_in_thread)
        thread.daemon = True
        thread.start()
    
    def stop_sequence(self):
        self.autoclicker.stop()
        messagebox.showinfo("停止", "已停止执行")
    
    def save_sequence(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.save_actions(filename):
                messagebox.showinfo("成功", "序列已保存")
            else:
                messagebox.showerror("错误", "保存失败")
    
    def load_sequence(self):
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.load_actions(filename):
                self.update_action_list()
                messagebox.showinfo("成功", "序列已加载")
            else:
                messagebox.showerror("错误", "加载失败")
    
    def save_script_txt(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.save_as_txt(filename):
                messagebox.showinfo("成功", "脚本已保存为文本文件")
            else:
                messagebox.showerror("错误", "保存文本文件失败")
    
    def load_script_txt(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            if self.autoclicker.load_from_txt(filename):
                self.update_action_list()
                messagebox.showinfo("成功", "脚本已从文本文件加载")
            else:
                messagebox.showerror("错误", "加载文本文件失败")
    
    def toggle_safety(self):
        if self.safety_var.get():
            pyautogui.FAILSAFE = True
        else:
            pyautogui.FAILSAFE = False
    
    def minimize_to_tray(self):
        """最小化到系统托盘"""
        if PYSTRAY_AVAILABLE and self.tray_icon:
            self.window.withdraw()
            self.is_hidden = True
            
            # 在后台线程中运行托盘图标
            if not hasattr(self, 'tray_thread') or not self.tray_thread.is_alive():
                self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                self.tray_thread.start()
            print("程序已最小化到系统托盘，全局热键仍可用")
        else:
            # 如果没有系统托盘支持，则最小化到任务栏
            self.window.iconify()
            print("程序已最小化")
    
    def show_window(self):
        """从托盘恢复窗口"""
        if self.is_hidden:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self.is_hidden = False
            
            # 停止托盘图标
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except:
                    pass
            print("主窗口已显示")
        else:
            self.window.deiconify()
    
    def toggle_window_visibility(self):
        """切换窗口可见性"""
        if self.window.winfo_viewable():
            self.minimize_to_tray()
        else:
            self.show_window()
    
    def on_closing(self):
        """窗口关闭事件"""
        self.clear_position_cache()
        self.quit_application()
    
    def quit_application(self):
        """退出应用程序"""
        self.stop_hotkey_listener()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass
        self.window.quit()
        self.window.destroy()
        os._exit(0)
    
    def run(self):
        """启动GUI"""
        self.window.mainloop()

def check_dependencies():
    """检查依赖库"""
    print("=" * 60)
    print("自动化脚本 v6.0 - 精简版")
    print("=" * 60)
    
    missing = []
    
    # 检查核心库
    try:
        import pyautogui
        print("✓ pyautogui")
    except ImportError:
        missing.append("pyautogui")
        print("✗ pyautogui")
    
    # 检查pynput库
    try:
        from pynput import mouse, keyboard
        print("✓ pynput")
    except ImportError:
        missing.append("pynput")
        print("✗ pynput")
    
    # 检查可选库
    try:
        import pystray
        from PIL import Image
        print("✓ pystray + PIL (系统托盘)")
    except ImportError:
        print("✗ pystray + PIL (系统托盘)")
    
    print("=" * 60)
    
    if missing:
        print("缺少核心依赖库，请运行以下命令安装：")
        print("pip install " + " ".join(missing))
        print("\n或者使用镜像源加速安装：")
        print("pip install " + " ".join(missing) + " -i https://pypi.tuna.tsinghua.edu.cn/simple")
        
        response = messagebox.askyesno("依赖库缺失", 
            f"缺少以下核心依赖库：{', '.join(missing)}\n\n"
            "是否立即安装？\n\n"
            "注意：需要管理员权限。")
        
        if response:
            try:
                import subprocess
                subprocess.run(f"pip install {' '.join(missing)} -i https://pypi.tuna.tsinghua.edu.cn/simple", 
                             shell=True, check=True)
                print("依赖库安装完成！")
                return True
            except Exception as e:
                print(f"安装依赖库失败: {e}")
                messagebox.showerror("安装失败", "请手动安装依赖库。")
                return False
    
    return True

def main():
    """主函数"""
    try:
        # 检查依赖
        if not check_dependencies():
            return
        
        # 创建并运行应用
        app = AutoClickerGUI()
        app.run()
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        messagebox.showerror("启动失败", 
            f"程序启动失败:\n\n{str(e)}\n\n"
            "请检查：\n"
            "1. 是否以管理员身份运行\n"
            "2. 依赖库是否安装完整\n"
            "3. 防病毒软件是否阻止了程序")

if __name__ == "__main__":
    main()
