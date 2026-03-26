"""自动化脚本 """
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
from datetime import datetime
# 引入 webbrowser 用于打开链接
import webbrowser

# ============================================================================
# 库导入和变量定义
# ============================================================================

# 导入 pydirectinput（游戏优化库）
PYDIRECTINPUT_AVAILABLE = False
pydirectinput = None
try:
    import pydirectinput
    PYDIRECTINPUT_AVAILABLE = True
    print("√ pydirectinput 库加载成功（全屏游戏优化）")
except Exception as e:
    print(f"× 无法加载 pydirectinput 库：{e}")
    PYDIRECTINPUT_AVAILABLE = False

# 尝试导入 pynput 库（事件监听、录制和全局热键）
PYNPUT_AVAILABLE = False
pynput_mouse = None
pynput_keyboard = None
global_hotkey_listener = None  # 用于全局热键监听的实例
try:
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
    print("√ pynput 库加载成功（事件监听、录制及全局热键）")
except Exception as e:
    print(f"× 无法加载 pynput 库：{e}")
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

# ============================================================================
# AutoClicker 类
# ============================================================================

class AutoClicker:
    def __init__(self, use_pydirectinput=True):
        self.running = False
        self.actions = []
        self.current_action_index = 0
        self.use_pydirectinput = use_pydirectinput and PYDIRECTINPUT_AVAILABLE

        # 录制相关变量
        self.recording = False
        self.recorded_actions = []
        self.recording_start_time = 0
        self.last_action_time = 0
        self.current_text_buffer = ""  # 用于记录连续的文本输入
        self.last_key_press_time = 0
        self.text_input_threshold = 0.3  # 文本输入的时间阈值（秒）

        # pynput 监听器
        self.mouse_listener = None
        self.keyboard_listener = None

        if self.use_pydirectinput:
            print("✓ 使用 pydirectinput 进行输入模拟（全屏游戏优化）")
        else:
            print("⚠ 使用 pyautogui 进行输入模拟")

    def move_mouse(self, x, y, duration=0.5):
        try:
            if self.use_pydirectinput and pydirectinput:
                # pydirectinput 不支持 duration 参数，需要手动实现
                if duration > 0:
                    import pyautogui
                    start_x, start_y = pyautogui.position()
                    steps = int(duration * 10)  # 每 0.1 秒移动一次
                    if steps > 0:
                        for i in range(steps + 1):
                            progress = i / steps
                            current_x = start_x + (x - start_x) * progress
                            current_y = start_y + (y - start_y) * progress
                            pydirectinput.moveTo(int(current_x), int(current_y))
                            time.sleep(duration / steps)
                    else:
                        pydirectinput.moveTo(x, y)
                else:
                    pydirectinput.moveTo(x, y)
            else:
                pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            print(f"移动鼠标出错：{e}")
            return False

    def click_mouse(self, button='left', clicks=1, interval=0.1):
        try:
            if self.use_pydirectinput and pydirectinput:
                if button == 'left':
                    for _ in range(clicks):
                        pydirectinput.leftClick()
                        if clicks > 1 and interval > 0:
                            time.sleep(interval)
                elif button == 'right':
                    for _ in range(clicks):
                        pydirectinput.rightClick()
                        if clicks > 1 and interval > 0:
                            time.sleep(interval)
                elif button == 'middle':
                    for _ in range(clicks):
                        pydirectinput.middleClick()
                        if clicks > 1 and interval > 0:
                            time.sleep(interval)
            else:
                pyautogui.click(button=button, clicks=clicks, interval=interval)
            return True
        except Exception as e:
            print(f"鼠标点击出错：{e}")
            return False

    def double_click(self, button='left'):
        return self.click_mouse(button=button, clicks=2, interval=0.1)

    def right_click(self):
        return self.click_mouse(button='right')

    def scroll(self, clicks):
        try:
            if self.use_pydirectinput and pydirectinput:
                # pydirectinput 可能没有 scroll 方法，使用 pyautogui
                pyautogui.scroll(clicks)
            else:
                pyautogui.scroll(clicks)
            return True
        except Exception as e:
            print(f"滚动出错：{e}")
            return False

    def press_key(self, key, presses=1, interval=0.1):
        try:
            if self.use_pydirectinput and pydirectinput:
                for _ in range(presses):
                    pydirectinput.press(key)
                    if presses > 1 and interval > 0:
                        time.sleep(interval)
            else:
                pyautogui.press(key, presses=presses, interval=interval)
            return True
        except Exception as e:
            print(f"按键出错：{e}")
            return False

    def type_text(self, text, interval=0.1):
        """直接输入文本"""
        try:
            if self.use_pydirectinput and pydirectinput:
                # pydirectinput 的 write 函数自动处理特殊字符
                pydirectinput.write(text, interval=interval)
            else:
                # 使用 pyautogui 的 write 函数直接输入文本
                pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            print(f"输入文本出错：{e}")
            return False

    def hotkey(self, *keys):
        try:
            if self.use_pydirectinput and pydirectinput:
                # 处理多个按键的组合
                for key in keys:
                    pydirectinput.keyDown(key)
                for key in reversed(keys):
                    pydirectinput.keyUp(key)
            else:
                pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"组合键出错：{e}")
            return False

    def drag_mouse(self, x, y, duration=0.5, button='left'):
        try:
            if self.use_pydirectinput and pydirectinput:
                # pydirectinput 的 dragTo 函数
                pydirectinput.dragTo(x, y, duration=duration, button=button)
            else:
                pyautogui.dragTo(x, y, duration=duration, button=button)
            return True
        except Exception as e:
            print(f"拖拽出错：{e}")
            return False

    def wait(self, seconds):
        time.sleep(seconds)
        return True

    def get_current_position(self):
        if self.use_pydirectinput and pydirectinput:
            # pydirectinput 没有 position() 函数，使用 pyautogui
            import pyautogui
            return pyautogui.position()
        else:
            return pyautogui.position()

    def get_screen_size(self):
        if self.use_pydirectinput and pydirectinput:
            # pydirectinput 没有 size() 函数，使用 pyautogui
            import pyautogui
            return pyautogui.size()
        else:
            return pyautogui.size()

    def get_active_window_title(self):
        """获取当前活动窗口标题（用于全屏游戏检测）"""
        try:
            import pygetwindow as gw
            active_window = gw.getActiveWindow()
            if active_window:
                return active_window.title
            return None
        except:
            return None

    def mouse_down_action(self, button='left', x=None, y=None):
        """鼠标按下（长按开始）"""
        try:
            if x is not None and y is not None:
                self.move_mouse(x, y)
            if self.use_pydirectinput and pydirectinput:
                if button == 'left':
                    pydirectinput.mouseDown(button='left')
                elif button == 'right':
                    pydirectinput.mouseDown(button='right')
                elif button == 'middle':
                    pydirectinput.mouseDown(button='middle')
            else:
                pyautogui.mouseDown(button=button)
            return True
        except Exception as e:
            print(f"鼠标按下出错：{e}")
            return False

    def mouse_up_action(self, button='left'):
        """鼠标释放（长按结束）"""
        try:
            if self.use_pydirectinput and pydirectinput:
                if button == 'left':
                    pydirectinput.mouseUp(button='left')
                elif button == 'right':
                    pydirectinput.mouseUp(button='right')
                elif button == 'middle':
                    pydirectinput.mouseUp(button='middle')
            else:
                pyautogui.mouseUp(button=button)
            return True
        except Exception as e:
            print(f"鼠标释放出错：{e}")
            return False

    def add_action(self, action_type, **kwargs):
        action = {
            'type': action_type,
            'kwargs': kwargs,
            'timestamp': time.time(),
            'recorded': True  # 标记为录制动作
        }
        self.actions.append(action)
        return action

    def insert_action_at(self, index, action_type, **kwargs):
        """在指定位置插入动作"""
        action = {
            'type': action_type,
            'kwargs': kwargs,
            'timestamp': time.time(),
            'recorded': True
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
                # 添加引擎信息
                data = {
                    'engine': 'pydirectinput' if self.use_pydirectinput else 'pyautogui',
                    'version': '4.0',
                    'recorded': any(action.get('recorded', False) for action in self.actions),
                    'actions': self.actions
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存出错：{e}")
            return False

    def load_actions(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.actions = data.get('actions', [])
                # 可以在这里读取引擎设置，但保持当前设置
            return True
        except Exception as e:
            print(f"加载出错：{e}")
            return False

    def save_as_txt(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# 鼠标键盘自动化脚本\n")
                f.write(f"# 引擎：{'pydirectinput' if self.use_pydirectinput else 'pyautogui'}\n")
                f.write(f"# 版本：1.0 \n")
                f.write(f"# 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# 此文件由自动化工具生成，可以直接编辑\n")
                f.write("# 格式：类型 参数=值\n")
                f.write("# 支持的动作类型：move, click, double_click, right_click, scroll, press, type, hotkey, drag, wait, mousedown, mouseup\n")
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
            print(f"保存为文本文件出错：{e}")
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
                        'timestamp': time.time(),
                        'recorded': False
                    }
                    actions.append(action)
                self.actions = actions
            return True
        except Exception as e:
            print(f"从文本文件加载出错：{e}")
            return False

    def run_actions(self, repeat=1, interval=0, target_window=None):
        """ 执行动作序列
        target_window: 目标窗口标题（可选），如果指定，将检查当前活动窗口
        """
        self.running = True
        self.current_action_index = 0
        for repeat_count in range(repeat):
            if not self.running:
                break
            for i, action in enumerate(self.actions):
                if not self.running:
                    break
                # 检查目标窗口（如果指定了）
                if target_window:
                    current_window = self.get_active_window_title()
                    if current_window and target_window not in current_window:
                        print(f"警告：当前窗口不是目标窗口，暂停执行")
                        while self.running and target_window not in (self.get_active_window_title() or ""):
                            time.sleep(0.5)
                            if not self.running:
                                break
                        print(f"已切换到目标窗口，继续执行")
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
                elif action_type == 'mousedown':
                    self.mouse_down_action(**kwargs)
                elif action_type == 'mouseup':
                    self.mouse_up_action(**kwargs)
                if interval > 0 and i < len(self.actions) - 1:
                    time.sleep(interval)
            if repeat_count < repeat - 1 and interval > 0:
                time.sleep(interval)
        self.running = False

    def stop(self):
        self.running = False

    # ============================================================================
    # pynput 事件监听和录制功能 
    # ============================================================================

    def start_recording(self):
        """开始录制鼠标和键盘事件"""
        if not PYNPUT_AVAILABLE:
            print("错误：pynput 库不可用，无法录制")
            return False
        if self.recording:
            print("警告：录制已在运行中")
            return False
        self.recording = True
        self.recorded_actions = []
        self.recording_start_time = time.time()
        self.last_action_time = self.recording_start_time
        self.current_text_buffer = ""
        self.last_key_press_time = 0
        print("开始录制...")
        print("提示：移动鼠标、点击、按键等操作将被记录")
        print("按 F9 键停止录制")

        # 启动鼠标监听器
        try:
            self.mouse_listener = mouse.Listener(
                on_move=self._on_move_record,
                on_click=self._on_click_record,
                on_scroll=self._on_scroll_record
            )
            self.mouse_listener.start()
        except Exception as e:
            print(f"启动鼠标监听器失败：{e}")
            self.recording = False
            return False

        # 启动键盘监听器
        try:
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_press_record,
                on_release=self._on_release_record
            )
            self.keyboard_listener.start()
        except Exception as e:
            print(f"启动键盘监听器失败：{e}")
            # 停止已启动的监听器
            if self.mouse_listener:
                self.mouse_listener.stop()
            self.recording = False
            return False
        return True

    def stop_recording(self):
        """停止录制并返回录制的动作"""
        if not self.recording:
            print("警告：录制未运行")
            return []
        self.recording = False

        # 停止监听器并等待它们完全停止
        try:
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
        except Exception as e:
            print(f"停止监听器时出错：{e}")

        # 处理最后可能剩余的文本缓冲
        if self.current_text_buffer:
            self._add_recorded_action('type', text=self.current_text_buffer)
            self.current_text_buffer = ""

        recording_duration = time.time() - self.recording_start_time
        print(f"录制停止，共录制了 {len(self.recorded_actions)} 个动作，持续时间：{recording_duration:.2f}秒")

        # 将录制的动作添加到主动作列表
        self.actions.extend(self.recorded_actions)
        return self.recorded_actions

    def _on_move_record(self, x, y):
        """鼠标移动事件处理器"""
        try:
            if not self.recording:
                return
            current_time = time.time()
            time_since_last = current_time - self.last_action_time
            # 只记录有意义的鼠标移动（避免记录太多微小的移动）
            if time_since_last > 0.1:  # 至少 0.1 秒间隔
                # 检查是否有未处理的文本缓冲
                if self.current_text_buffer:
                    self._add_recorded_action('type', text=self.current_text_buffer)
                    self.current_text_buffer = ""
                self._add_recorded_action('move', x=x, y=y)
                self.last_action_time = current_time
        except Exception as e:
            print(f"处理鼠标移动事件时出错：{e}")

    def _on_click_record(self, x, y, button, pressed):
        """鼠标点击事件处理器"""
        try:
            if not self.recording or not pressed:
                return
            current_time = time.time()
            # 检查是否有未处理的文本缓冲
            if self.current_text_buffer:
                self._add_recorded_action('type', text=self.current_text_buffer)
                self.current_text_buffer = ""
            button_name = str(button).split('.')[-1]
            if button_name == 'left':
                # 检查是否是双击
                time_since_last_click = current_time - self.last_action_time
                if time_since_last_click < 0.3:  # 双击时间阈值
                    # 移除上一个左键点击，替换为双击
                    if (self.recorded_actions and 
                        self.recorded_actions[-1]['type'] == 'click' and 
                        self.recorded_actions[-1]['kwargs'].get('button') == 'left'):
                        self.recorded_actions.pop()
                        self._add_recorded_action('double_click')
                    else:
                        self._add_recorded_action('click', button='left', x=x, y=y)
                else:
                    self._add_recorded_action('click', button='left', x=x, y=y)
            elif button_name == 'right':
                self._add_recorded_action('click', button='right', x=x, y=y)
            elif button_name == 'middle':
                self._add_recorded_action('click', button='middle', x=x, y=y)
            self.last_action_time = current_time
        except Exception as e:
            print(f"处理鼠标点击事件时出错：{e}")

    def _on_scroll_record(self, x, y, dx, dy):
        """鼠标滚轮事件处理器"""
        try:
            if not self.recording:
                return
            current_time = time.time()
            # 检查是否有未处理的文本缓冲
            if self.current_text_buffer:
                self._add_recorded_action('type', text=self.current_text_buffer)
                self.current_text_buffer = ""
            # 智能处理 dy 值，确保非零滚动事件不被丢弃
            if dy > 0:
                scroll_amount = max(1, int(dy))  # 向上滚动，至少为1
            elif dy < 0:
                scroll_amount = min(-1, int(dy))  # 向下滚动，最多为-1
            else:
                scroll_amount = 0  # dy == 0，无滚动
            if scroll_amount != 0:
                self._add_recorded_action('scroll', clicks=scroll_amount)
            self.last_action_time = current_time
        except Exception as e:
            print(f"处理鼠标滚轮事件时出错：{e}")

    def _on_press_record(self, key):
        """键盘按下事件处理器"""
        try:
            if not self.recording:
                return
            current_time = time.time()

            # 处理特殊按键
            if key == keyboard.Key.f9:  # F9 键用于停止录制
                self.stop_recording()
                return

            # 处理修饰键
            if key in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
                       keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
                       keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
                       keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r]:
                # 修饰键单独处理，不记录
                return

            # 处理功能键
            if hasattr(key, 'name'):
                if key.name.startswith('f'):  # 功能键
                    self._flush_text_buffer()
                    self._add_recorded_action('press', key=key.name)
                    self.last_key_press_time = current_time
                    self.last_action_time = current_time
                elif key.name in ['enter', 'tab', 'space', 'esc', 'backspace', 'delete', 'insert',
                                  'home', 'end', 'page_up', 'page_down', 'up', 'down', 'left', 'right']:
                    # 特殊按键
                    self._flush_text_buffer()
                    self._add_recorded_action('press', key=key.name)
                    self.last_key_press_time = current_time
                    self.last_action_time = current_time
                else:
                    # 其他命名按键
                    self._flush_text_buffer()
                    self._add_recorded_action('press', key=key.name)
                    self.last_key_press_time = current_time
                    self.last_action_time = current_time
            else:
                # 字符按键
                time_since_last_key = current_time - self.last_key_press_time
                if time_since_last_key < self.text_input_threshold:
                    # 快速连续按键，视为文本输入
                    char = getattr(key, 'char', None)
                    if char and char.isprintable():
                        self.current_text_buffer += char
                    else:
                        # 超过阈值，处理之前的缓冲
                        self._flush_text_buffer()
                        # 开始新的文本缓冲
                        char = getattr(key, 'char', None)
                        if char and char.isprintable():
                            self.current_text_buffer = char
                else:
                    # 超过阈值，处理之前的缓冲
                    self._flush_text_buffer()
                    # 开始新的文本缓冲
                    char = getattr(key, 'char', None)
                    if char and char.isprintable():
                        self.current_text_buffer = char
                self.last_key_press_time = current_time
        except Exception as e:
            print(f"处理键盘事件时出错：{e}")

    def _on_release_record(self, key):
        """键盘释放事件处理器（主要用于组合键检测）"""
        try:
            if not self.recording:
                return
        except Exception as e:
            print(f"处理键盘释放事件时出错：{e}")

    def _flush_text_buffer(self):
        """将文本缓冲保存为动作"""
        if self.current_text_buffer:
            # 只有当文本缓冲不为空时才添加动作
            action = {
                'type': 'type',
                'kwargs': {'text': self.current_text_buffer},
                'timestamp': time.time(),
                'recorded': True
            }
            self.recorded_actions.append(action)
            print(f"添加文本动作：{self.current_text_buffer}")
            self.current_text_buffer = ""
            self.last_action_time = time.time()

    def _add_recorded_action(self, action_type, **kwargs):
        """添加录制的动作"""
        try:
            current_time = time.time()
            # 如果是第一个动作，不添加等待
            if self.recorded_actions:
                # 计算与上一个动作的时间间隔
                time_since_last = current_time - self.last_action_time
                if time_since_last > 0.1:  # 添加等待动作（如果间隔大于 0.1 秒）
                    wait_action = {
                        'type': 'wait',
                        'kwargs': {'seconds': round(time_since_last, 2)},
                        'timestamp': current_time - time_since_last,
                        'recorded': True
                    }
                    self.recorded_actions.append(wait_action)
            # 添加当前动作
            action = {
                'type': action_type,
                'kwargs': kwargs,
                'timestamp': current_time,
                'recorded': True
            }
            self.recorded_actions.append(action)
            print(f"录制动作：{action_type} {kwargs}")
        except Exception as e:
            print(f"添加录制动作时出错：{e}")

# ============================================================================
# GUI 类
# ============================================================================

class AutoClickerGUI:
    def __init__(self):
        # 读取配置文件
        self.config_file = "autoclicker_config.json"
        self.load_config()

        # 根据配置初始化 AutoClicker
        self.autoclicker = AutoClicker(use_pydirectinput=self.config.get('use_pydirectinput', True))
        self.window = tk.Tk()
        self.window.title(f"鼠标键盘自动化控制 v1.0（引擎：{'pydirectinput' if self.autoclicker.use_pydirectinput else 'pyautogui'}）")
        self.window.geometry("1000x900")

        # 系统托盘变量
        self.tray_icon = None
        self.is_hidden = False

        # 热键管理变量 - 使用 pynput 监听器
        self.hotkey_listener = None
        self.pressed_keys = set()  # 用于跟踪组合键状态

        # 目标窗口变量
        self.target_window_var = tk.StringVar(value=self.config.get('target_window', ''))

        # 录制状态变量
        self.recording_var = tk.BooleanVar(value=False)
        self.recording_status_var = tk.StringVar(value="未录制")

        # 设置窗口关闭行为
        self.window.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')

        # 创建 UI
        self.setup_ui()

        # 检查管理员权限
        self.check_admin_privileges()

        # 设置全局热键 (使用 pynput)
        self.setup_global_hotkeys()

        # 设置安全功能
        self.toggle_safety()

    def load_config(self):
        """加载配置文件"""
        self.config = {
            'use_pydirectinput': True,
            'target_window': '',
            'safety_enabled': True,
            'recording_interval': 0.1
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                print(f"✓ 已加载配置文件：{self.config_file}")
            except Exception as e:
                print(f"× 加载配置文件失败：{e}")

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"✓ 已保存配置文件：{self.config_file}")
        except Exception as e:
            print(f"× 保存配置文件失败：{e}")

    def check_admin_privileges(self):
        """检查是否以管理员身份运行"""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("警告：未以管理员身份运行，全屏游戏快捷键可能失效")
                print("建议：右键点击程序 -> '以管理员身份运行'")
                return False
            else:
                print("✓ 程序以管理员身份运行")
                return True
        except:
            print("无法检测管理员权限")
            return False

    def setup_ui(self):
        """创建 UI 界面"""
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.create_manual_tab(notebook)
        self.create_sequence_tab(notebook)
        self.create_recording_tab(notebook)  # 录制选项卡
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
                pystray.MenuItem("开始执行 (F2)", lambda: self.start_sequence()),
                pystray.MenuItem("停止执行 (F3)", lambda: self.stop_sequence()),
                pystray.MenuItem("开始录制 (F8)", lambda: self.start_recording()),
                pystray.MenuItem("停止录制 (F9)", lambda: self.stop_recording()),
                pystray.MenuItem("---", None),
                pystray.MenuItem("退出", self.quit_application)
            )
            self.tray_icon = pystray.Icon("auto_clicker", image, "自动化控制 v.0", menu)
        except Exception as e:
            print(f"创建托盘图标失败：{e}")

    def setup_global_hotkeys(self):
        """设置全局热键管理器 (使用 pynput)"""
        if not PYNPUT_AVAILABLE:
            print("× pynput 不可用，无法设置全局热键")
            return
        print("✓ 正在启动 pynput 全局热键监听器...")
        try:
            # 启动一个独立的监听器专门用于处理全局快捷键
            self.hotkey_listener = keyboard.Listener(
                on_press=self._on_hotkey_press,
                on_release=self._on_hotkey_release
            )
            self.hotkey_listener.start()
            print("✓ 全局热键监听器启动成功")
        except Exception as e:
            print(f"× 全局热键监听器启动失败：{e}")
            print(f"详细错误：{traceback.format_exc()}")
            messagebox.showerror("热键错误", f"注册全局快捷键失败:\n\n错误类型：{type(e).__name__}\n错误信息：{str(e)}\n\n"
                                           f"请确保：\n1. 以管理员身份运行本程序\n2. 检查防病毒软件是否阻止了键盘钩子")

    def _on_hotkey_press(self, key):
        """处理热键按下事件"""
        try:
            # 将按键转换为字符串以便比较
            key_str = self._get_key_string(key)
            if key_str:
                self.pressed_keys.add(key_str)

            # 检查组合键
            current_combination = sorted(list(self.pressed_keys))

            # 定义热键映射
            # Ctrl+Shift+P
            if {'ctrl', 'shift', 'p'}.issubset(self.pressed_keys):
                self.get_current_pos_from_shortcut()
            # Ctrl+Shift+W - 检测窗口
            elif {'ctrl', 'shift', 'w'}.issubset(self.pressed_keys):
                self.detect_current_window_from_shortcut()
            # F1: 暂停/恢复
            elif key == keyboard.Key.f1:
                self.toggle_pause_execution()
            # F2: 开始执行
            elif key == keyboard.Key.f2:
                self.start_sequence_global()
            # F3: 停止执行
            elif key == keyboard.Key.f3:
                self.stop_sequence_global()
            # F8: 开始录制
            elif key == keyboard.Key.f8:
                self.start_recording_global()
            # F9: 停止录制
            elif key == keyboard.Key.f9:
                self.stop_recording_global()
            # Ctrl+Shift+H: 显示/隐藏
            elif {'ctrl', 'shift', 'h'}.issubset(self.pressed_keys):
                self.toggle_window_visibility()
        except Exception as e:
            print(f"处理热键按下时出错：{e}")

    def _on_hotkey_release(self, key):
        """处理热键释放事件"""
        try:
            key_str = self._get_key_string(key)
            if key_str and key_str in self.pressed_keys:
                self.pressed_keys.remove(key_str)
        except Exception as e:
            print(f"处理热键释放时出错：{e}")

    def _get_key_string(self, key):
        """将 pynput key 对象转换为统一的字符串"""
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
        elif hasattr(key, 'name'):
            name = key.name
            # 规范化修饰键名称
            if name in ['ctrl_l', 'ctrl_r']:
                return 'ctrl'
            if name in ['shift_l', 'shift_r']:
                return 'shift'
            if name in ['alt_l', 'alt_r']:
                return 'alt'
            if name in ['cmd_l', 'cmd_r', 'win_l', 'win_r']:
                return 'cmd'  # 或者 win
            return name
        return None

    # ============================================================================
    # 快捷键处理函数
    # ============================================================================

    def get_current_pos_from_shortcut(self):
        """通过快捷键获取当前鼠标位置"""
        try:
            pos = self.autoclicker.get_current_position()
            if self.window.winfo_viewable():
                self.x_entry.delete(0, tk.END)
                self.x_entry.insert(0, str(pos.x))
                self.y_entry.delete(0, tk.END)
                self.y_entry.insert(0, str(pos.y))
            print(f"[热键] 获取位置：X={pos.x}, Y={pos.y}")
        except Exception as e:
            print(f"[热键] 获取位置失败：{e}")

    def detect_current_window_from_shortcut(self):
        """通过快捷键检测当前窗口"""
        try:
            window_title = self.autoclicker.get_active_window_title()
            if window_title:
                self.target_window_var.set(window_title)
                if self.window.winfo_viewable():
                    messagebox.showinfo("窗口检测", f"已检测到当前窗口：{window_title}")
                print(f"[热键] 检测窗口：{window_title}")
            else:
                print("[热键] 无法获取当前窗口标题")
        except Exception as e:
            print(f"[热键] 检测窗口失败：{e}")

    def toggle_pause_execution(self):
        """暂停/恢复执行"""
        if self.autoclicker.running:
            self.autoclicker.stop()
            print("[热键] 执行已暂停 (F1)")
        else:
            self.start_sequence()
            print("[热键] 执行已恢复 (F1)")

    def start_sequence_global(self):
        """全局快捷键开始执行"""
        if not self.autoclicker.running:
            print("[热键] 开始执行 (F2)")
            self.start_sequence()

    def stop_sequence_global(self):
        """全局快捷键停止执行"""
        if self.autoclicker.running:
            self.autoclicker.stop()
            print("[热键] 停止执行 (F3)")

    def start_recording_global(self):
        """全局快捷键开始录制"""
        if not self.autoclicker.recording:
            print("[热键] 开始录制 (F8)")
            self.start_recording()

    def stop_recording_global(self):
        """全局快捷键停止录制"""
        if self.autoclicker.recording:
            print("[热键] 停止录制 (F9)")
            self.stop_recording()

    def toggle_window_visibility(self):
        """切换窗口可见性"""
        if self.window.winfo_viewable():
            self.minimize_to_tray()
        else:
            self.show_window()

    # ============================================================================
    # 后台运行功能
    # ============================================================================

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

    def quit_application(self):
        """退出应用程序"""
        # 停止录制（如果正在录制）
        if self.autoclicker.recording:
            self.autoclicker.stop_recording()

        # 停止热键监听器
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except:
                pass

        self.save_config()  # 保存配置
        self.cleanup()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass
        self.window.quit()
        self.window.destroy()
        os._exit(0)

    # ============================================================================
    # UI 创建函数
    # ============================================================================

    def create_manual_tab(self, notebook):
        """创建手动控制选项卡"""
        manual_frame = ttk.Frame(notebook)
        notebook.add(manual_frame, text="手动控制")

        # 引擎信息显示
        engine_frame = ttk.LabelFrame(manual_frame, text="引擎状态", padding=5)
        engine_frame.pack(fill='x', padx=10, pady=5)

        engine_text = f"当前使用引擎：{'pydirectinput（全屏游戏优化）' if self.autoclicker.use_pydirectinput else 'pyautogui（标准模式）'}"
        engine_label = ttk.Label(engine_frame, text=engine_text, foreground="blue")
        engine_label.pack(anchor='w', pady=5)

        # 鼠标控制区域
        mouse_frame = ttk.LabelFrame(manual_frame, text="鼠标控制", padding=10)
        mouse_frame.pack(fill='x', padx=10, pady=5)

        # 坐标输入
        coord_frame = ttk.Frame(mouse_frame)
        coord_frame.pack(fill='x', pady=5)

        ttk.Label(coord_frame, text="X 坐标:").pack(side='left', padx=5)
        self.x_entry = ttk.Entry(coord_frame, width=10)
        self.x_entry.pack(side='left', padx=5)

        ttk.Label(coord_frame, text="Y 坐标:").pack(side='left', padx=5)
        self.y_entry = ttk.Entry(coord_frame, width=10)
        self.y_entry.pack(side='left', padx=5)

        ttk.Button(coord_frame, text="获取当前位置", 
                  command=self.get_current_pos).pack(side='left', padx=20)

        ttk.Button(coord_frame, text="移动到", 
                  command=self.move_to_pos).pack(side='left', padx=5)

        # 鼠标按钮
        btn_frame = ttk.Frame(mouse_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text="左键单击", 
                  command=lambda: self.autoclicker.click_mouse(button='left')).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="右键单击", 
                  command=lambda: self.autoclicker.click_mouse(button='right')).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="双击", 
                  command=self.autoclicker.double_click).pack(side='left', padx=5)

        # 长按功能
        long_press_frame = ttk.Frame(mouse_frame)
        long_press_frame.pack(fill='x', pady=5)

        ttk.Button(long_press_frame, text="左键长按", 
                  command=lambda: self.autoclicker.mouse_down_action(button='left')).pack(side='left', padx=5)
        ttk.Button(long_press_frame, text="左键松开", 
                  command=lambda: self.autoclicker.mouse_up_action(button='left')).pack(side='left', padx=5)
        ttk.Button(long_press_frame, text="右键长按", 
                  command=lambda: self.autoclicker.mouse_down_action(button='right')).pack(side='left', padx=5)
        ttk.Button(long_press_frame, text="右键松开", 
                  command=lambda: self.autoclicker.mouse_up_action(button='right')).pack(side='left', padx=5)

        # 滚动控制
        scroll_frame = ttk.Frame(mouse_frame)
        scroll_frame.pack(fill='x', pady=5)

        ttk.Label(scroll_frame, text="滚轮控制:").pack(side='left', padx=5)
        ttk.Button(scroll_frame, text="向上滚动", 
                  command=lambda: self.autoclicker.scroll(1)).pack(side='left', padx=5)
        ttk.Button(scroll_frame, text="向下滚动", 
                  command=lambda: self.autoclicker.scroll(-1)).pack(side='left', padx=5)

        # 滚动设置
        ttk.Button(scroll_frame, text="设置滚动量", 
                  command=self.set_scroll_amount).pack(side='left', padx=5)

        # 键盘控制区域
        keyboard_frame = ttk.LabelFrame(manual_frame, text="键盘控制", padding=10)
        keyboard_frame.pack(fill='x', padx=10, pady=5)

        # 文本输入
        text_frame = ttk.Frame(keyboard_frame)
        text_frame.pack(fill='x', pady=5)

        ttk.Label(text_frame, text="输入文本:").pack(side='left')
        self.text_entry = ttk.Entry(text_frame, width=30)
        self.text_entry.pack(side='left', padx=5)
        ttk.Button(text_frame, text="输入", 
                  command=self.type_text).pack(side='left')

        # 常用按键
        key_frame = ttk.Frame(keyboard_frame)
        key_frame.pack(fill='x', pady=5)

        keys = ['enter', 'tab', 'space', 'esc', 'backspace', 'delete']
        for key in keys:
            ttk.Button(key_frame, text=key.upper(), 
                      command=lambda k=key: self.autoclicker.press_key(k)).pack(side='left', padx=2)

        # 组合键
        hotkey_frame = ttk.Frame(keyboard_frame)
        hotkey_frame.pack(fill='x', pady=5)

        ttk.Button(hotkey_frame, text="Ctrl+C", 
                  command=lambda: self.autoclicker.hotkey('ctrl', 'c')).pack(side='left', padx=2)
        ttk.Button(hotkey_frame, text="Ctrl+V", 
                  command=lambda: self.autoclicker.hotkey('ctrl', 'v')).pack(side='left', padx=2)
        ttk.Button(hotkey_frame, text="Ctrl+A", 
                  command=lambda: self.autoclicker.hotkey('ctrl', 'a')).pack(side='left', padx=2)
        ttk.Button(hotkey_frame, text="Alt+Tab", 
                  command=lambda: self.autoclicker.hotkey('alt', 'tab')).pack(side='left', padx=2)

    def set_scroll_amount(self):
        """设置滚动量"""
        try:
            amount = simpledialog.askinteger("滚动量", "请输入滚动单位数量（正数向上，负数向下）:", 
                                            initialvalue=1, minvalue=-100, maxvalue=100)
            if amount is not None:
                self.autoclicker.scroll(amount)
                messagebox.showinfo("滚动", f"已执行滚动 {amount} 单位")
        except Exception as e:
            messagebox.showerror("错误", f"设置滚动量时出错：{e}")

    def create_sequence_tab(self, notebook):
        """创建动作序列选项卡"""
        seq_frame = ttk.Frame(notebook)
        notebook.add(seq_frame, text="动作序列")

        # 目标窗口设置
        target_frame = ttk.LabelFrame(seq_frame, text="目标窗口设置（全屏游戏优化）", padding=5)
        target_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(target_frame, text="目标窗口标题（部分匹配）:").pack(side='left', padx=5)
        ttk.Entry(target_frame, textvariable=self.target_window_var, width=30).pack(side='left', padx=5)
        ttk.Button(target_frame, text="检测当前窗口", 
                  command=self.detect_current_window).pack(side='left', padx=5)

        target_help = ttk.Label(target_frame, text="留空则在所有窗口执行，否则只在包含此标题的窗口中执行", 
                               foreground="gray")
        target_help.pack(side='left', padx=10)

        # 动作列表
        list_frame = ttk.LabelFrame(seq_frame, text="动作列表", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # 创建树形视图显示动作
        columns = ('序号', '类型', '参数', '录制', '时间')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        column_widths = {'序号': 50, '类型': 100, '参数': 300, '录制': 50, '时间': 100}
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=column_widths.get(col, 150))

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 添加右键菜单
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="在上方插入移动指令", command=self.insert_move_above)
        self.context_menu.add_command(label="在上方插入左键点击", command=lambda: self.insert_click_above('left'))
        self.context_menu.add_command(label="在上方插入右键点击", command=lambda: self.insert_click_above('right'))
        self.context_menu.add_command(label="在上方插入等待指令", command=self.insert_wait_above)
        self.context_menu.add_command(label="在上方插入按键指令", command=self.insert_key_above)
        self.context_menu.add_command(label="在上方插入拖拽指令", command=self.insert_drag_above)
        self.context_menu.add_command(label="在上方插入滚动指令", command=self.insert_scroll_above)
        self.context_menu.add_command(label="在上方插入鼠标长按", command=self.insert_mousedown_above)
        self.context_menu.add_command(label="在上方插入鼠标松开", command=self.insert_mouseup_above)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除选中", command=self.delete_selected_action)

        # 绑定右键菜单事件
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 动作控制按钮
        control_frame = ttk.Frame(seq_frame)
        control_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(control_frame, text="添加移动", 
                  command=self.add_move_action).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加左键点击", 
                  command=lambda: self.add_click_action('left')).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加右键点击", 
                  command=lambda: self.add_click_action('right')).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加等待", 
                  command=self.add_wait_action).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加按键", 
                  command=self.add_key_action).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加拖拽", 
                  command=self.add_drag_action).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加滚动", 
                  command=self.add_scroll_action).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加长按", 
                  command=self.add_mousedown_action).pack(side='left', padx=5)
        ttk.Button(control_frame, text="添加松开", 
                  command=self.add_mouseup_action).pack(side='left', padx=5)

        ttk.Button(control_frame, text="删除选中", 
                  command=self.delete_selected_action).pack(side='left', padx=20)
        ttk.Button(control_frame, text="清空列表", 
                  command=self.clear_action_list).pack(side='left', padx=5)

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

        ttk.Label(exec_control_frame, text="动作间隔 (秒):").pack(side='left', padx=10)
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

        ttk.Button(file_frame, text="保存序列 (.json)", 
                  command=self.save_sequence).pack(side='left', padx=5)
        ttk.Button(file_frame, text="加载序列 (.json)", 
                  command=self.load_sequence).pack(side='left', padx=5)
        ttk.Button(file_frame, text="保存脚本 (.txt)", 
                  command=self.save_script_txt).pack(side='left', padx=5)
        ttk.Button(file_frame, text="加载脚本 (.txt)", 
                  command=self.load_script_txt).pack(side='left', padx=5)

    def create_recording_tab(self, notebook):
        """创建录制控制选项卡"""
        recording_frame = ttk.Frame(notebook)
        notebook.add(recording_frame, text="动作录制")

        # 录制状态显示
        status_frame = ttk.LabelFrame(recording_frame, text="录制状态", padding=10)
        status_frame.pack(fill='x', padx=10, pady=5)

        # 状态指示灯
        indicator_frame = ttk.Frame(status_frame)
        indicator_frame.pack(fill='x', pady=5)

        self.recording_indicator = tk.Canvas(indicator_frame, width=20, height=20, bg='white')
        self.recording_indicator.pack(side='left', padx=5)
        self.update_recording_indicator()

        ttk.Label(indicator_frame, textvariable=self.recording_status_var, 
                 font=('Arial', 12, 'bold')).pack(side='left', padx=10)

        # 录制统计
        stats_frame = ttk.Frame(status_frame)
        stats_frame.pack(fill='x', pady=5)

        self.recording_stats_var = tk.StringVar(value="动作数量：0 | 录制时间：0 秒")
        ttk.Label(stats_frame, textvariable=self.recording_stats_var).pack(anchor='w')

        # 录制控制按钮
        control_frame = ttk.LabelFrame(recording_frame, text="录制控制", padding=10)
        control_frame.pack(fill='x', padx=10, pady=5)

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text="开始录制 (F8)", 
                  command=self.start_recording, 
                  style="Accent.TButton").pack(side='left', padx=5)
        ttk.Button(btn_frame, text="停止录制 (F9)", 
                  command=self.stop_recording).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="清除录制", 
                  command=self.clear_recording).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="应用录制到列表", 
                  command=self.apply_recording).pack(side='left', padx=5)

        # 录制设置
        settings_frame = ttk.LabelFrame(recording_frame, text="录制设置", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=5)

        # 文本输入阈值设置
        threshold_frame = ttk.Frame(settings_frame)
        threshold_frame.pack(fill='x', pady=5)

        ttk.Label(threshold_frame, text="文本输入识别阈值 (秒):").pack(side='left')
        self.text_threshold_var = tk.StringVar(value=str(self.config.get('recording_interval', 0.3)))
        threshold_spin = ttk.Spinbox(threshold_frame, from_=0.1, to=1.0, 
                                    increment=0.1, textvariable=self.text_threshold_var, width=5)
        threshold_spin.pack(side='left', padx=5)
        ttk.Button(threshold_frame, text="保存设置", 
                  command=self.save_recording_settings).pack(side='left', padx=10)

        # 录制选项
        options_frame = ttk.Frame(settings_frame)
        options_frame.pack(fill='x', pady=5)

        self.record_mouse_var = tk.BooleanVar(value=True)
        self.record_keyboard_var = tk.BooleanVar(value=True)
        self.auto_add_waits_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text="录制鼠标事件", 
                       variable=self.record_mouse_var).pack(anchor='w')
        ttk.Checkbutton(options_frame, text="录制键盘事件", 
                       variable=self.record_keyboard_var).pack(anchor='w')
        ttk.Checkbutton(options_frame, text="自动添加等待时间", 
                       variable=self.auto_add_waits_var).pack(anchor='w')

        # 录制说明
        help_frame = ttk.LabelFrame(recording_frame, text="使用说明", padding=10)
        help_frame.pack(fill='x', padx=10, pady=5)

        help_text = """录制功能说明：
        1. 点击"开始录制"或按 F8 键开始录制鼠标和键盘操作
        2. 进行您想要自动化的操作（移动鼠标、点击、输入文字等）
        3. 点击"停止录制"或按 F9 键停止录制
        4. 点击"应用录制到列表"将录制的动作添加到动作序列中
        5. 可以在"动作序列"标签页中编辑、保存或执行录制的动作

        注意事项：
        - 录制期间，程序会最小化到系统托盘
        - 文本输入会自动识别并合并为 type 动作
        - 快速连续点击会自动识别为双击
        - 录制过程中可以正常使用其他程序
        """

        help_label = ttk.Label(help_frame, text=help_text, justify='left')
        help_label.pack(anchor='w')

        # 设置强调按钮样式
        style = ttk.Style()
        style.configure("Accent.TButton", foreground="white", background="red")

    def update_recording_indicator(self):
        """更新录制状态指示灯"""
        self.recording_indicator.delete("all")
        if self.autoclicker.recording:
            # 红色闪烁效果
            if int(time.time() * 2) % 2 == 0:
                self.recording_indicator.create_oval(2, 2, 18, 18, fill="red", outline="red")
            else:
                self.recording_indicator.create_oval(2, 2, 18, 18, fill="darkred", outline="darkred")
            self.recording_status_var.set("正在录制...")
        else:
            self.recording_indicator.create_oval(2, 2, 18, 18, fill="green", outline="green")
            self.recording_status_var.set("准备就绪")

        # 更新统计信息
        if hasattr(self.autoclicker, 'recording_start_time') and self.autoclicker.recording_start_time > 0:
            duration = time.time() - self.autoclicker.recording_start_time
            action_count = len(self.autoclicker.recorded_actions)
            self.recording_stats_var.set(f"动作数量：{action_count} | 录制时间：{duration:.1f}秒")

        # 每秒更新一次
        self.window.after(500, self.update_recording_indicator)

    def save_recording_settings(self):
        """保存录制设置"""
        try:
            threshold = float(self.text_threshold_var.get())
            if 0.1 <= threshold <= 1.0:
                self.autoclicker.text_input_threshold = threshold
                self.config['recording_interval'] = threshold
                self.save_config()
                messagebox.showinfo("成功", f"文本输入识别阈值已设置为 {threshold} 秒")
            else:
                messagebox.showerror("错误", "阈值必须在 0.1 到 1.0 秒之间")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")

    def start_recording(self):
        """开始录制"""
        if not PYNPUT_AVAILABLE:
            messagebox.showerror("错误", "pynput 库未安装，无法使用录制功能\n请运行：pip install pynput")
            return

        if self.autoclicker.recording:
            messagebox.showwarning("警告", "录制已在运行中")
            return

        # 确认开始录制
        if not messagebox.askyesno("开始录制", 
                                  "即将开始录制鼠标和键盘操作。\n\n"
                                  "提示：\n"
                                  "1. 按 F9 键可停止录制\n"
                                  "2. 录制期间程序会最小化\n"
                                  "3. 文本输入会自动识别\n\n"
                                  "是否开始录制？"):
            return

        # 开始录制
        success = self.autoclicker.start_recording()
        if success:
            # 最小化到托盘
            self.minimize_to_tray()

            # 显示通知
            messagebox.showinfo("开始录制", 
                              "录制已开始！\n\n"
                              "提示：\n"
                              "1. 按 F9 键停止录制\n"
                              "2. 录制期间程序在系统托盘中\n"
                              "3. 文本输入会自动识别和合并")
        else:
            messagebox.showerror("错误", "开始录制失败")

    def stop_recording(self):
        """停止录制"""
        if not self.autoclicker.recording:
            messagebox.showwarning("警告", "没有正在进行的录制")
            return

        # 停止录制
        recorded_actions = self.autoclicker.stop_recording()

        # 显示录制结果
        if recorded_actions:
            action_count = len(recorded_actions)
            duration = time.time() - self.autoclicker.recording_start_time

            # 显示主窗口
            self.show_window()

            messagebox.showinfo("录制完成", 
                              f"录制完成！\n\n"
                              f"统计信息：\n"
                              f"- 录制动作数量：{action_count}\n"
                              f"- 录制持续时间：{duration:.1f}秒\n"
                              f"- 平均间隔：{duration/action_count:.2f}秒/动作\n\n"
                              f"点击'应用录制到列表'将动作添加到序列中")
        else:
            messagebox.showinfo("录制停止", "录制已停止，未录制到任何动作")

    def clear_recording(self):
        """清除录制结果"""
        if messagebox.askyesno("确认", "确定要清除所有录制的动作吗？"):
            self.autoclicker.recorded_actions = []
            messagebox.showinfo("成功", "已清除所有录制的动作")

    def apply_recording(self):
        """将录制的动作应用到动作列表"""
        if not self.autoclicker.recorded_actions:
            messagebox.showwarning("警告", "没有录制的动作可以应用")
            return

        # 将录制的动作添加到主动作列表
        self.autoclicker.actions.extend(self.autoclicker.recorded_actions)

        # 更新动作列表显示
        self.update_action_list()

        # 显示结果
        action_count = len(self.autoclicker.recorded_actions)
        messagebox.showinfo("成功", f"已成功添加 {action_count} 个录制的动作到动作序列")

        # 切换到动作序列标签页
        notebook = self.window.winfo_children()[0]  # 获取 Notebook
        notebook.select(1)  # 切换到第二个标签页（动作序列）

    def detect_current_window(self):
        """检测当前活动窗口"""
        try:
            window_title = self.autoclicker.get_active_window_title()
            if window_title:
                self.target_window_var.set(window_title)
                messagebox.showinfo("窗口检测", f"已检测到当前窗口：{window_title}")
            else:
                messagebox.showwarning("窗口检测", "无法获取当前窗口标题，请确保 pygetwindow 库已安装")
        except Exception as e:
            messagebox.showerror("错误", f"检测窗口时出错：{e}")

    def create_settings_tab(self, notebook):
        """创建设置选项卡"""
        # 创建一个可滚动的框架容器
        container = ttk.Frame(notebook)
        notebook.add(container, text="设置与帮助")

        # 创建 Canvas 和 Scrollbar
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        settings_frame = ttk.Frame(canvas)

        # 配置 canvas
        settings_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # 在 canvas 中创建窗口
        canvas.create_window((0, 0), window=settings_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 布局 canvas 和 scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮事件
        def _on_mouse_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mouse_wheel)

        # 引擎设置
        engine_frame = ttk.LabelFrame(settings_frame, text="引擎设置", padding=10)
        engine_frame.pack(fill='x', padx=10, pady=5)

        engine_status_text = f"当前引擎：{'pydirectinput' if self.autoclicker.use_pydirectinput else 'pyautogui'}"
        engine_status_label = ttk.Label(engine_frame, text=engine_status_text, foreground="blue")
        engine_status_label.pack(anchor='w', pady=5)

        engine_desc_text = """引擎说明:
        • pydirectinput: 专门为游戏设计，可绕过 DirectX 输入限制，全屏游戏兼容性最佳
        • pyautogui: 标准桌面自动化库，适用于普通应用程序
        """
        engine_desc_label = ttk.Label(engine_frame, text=engine_desc_text, justify='left')
        engine_desc_label.pack(anchor='w', padx=5)

        # 切换引擎按钮
        if PYDIRECTINPUT_AVAILABLE:
            engine_btn_frame = ttk.Frame(engine_frame)
            engine_btn_frame.pack(anchor='w', pady=5)

            if self.autoclicker.use_pydirectinput:
                ttk.Button(engine_btn_frame, text="切换到 pyautogui 模式", 
                        command=self.switch_to_pyautogui).pack(side='left', padx=5)
            else:
                ttk.Button(engine_btn_frame, text="切换到 pydirectinput 模式（游戏优化）", 
                        command=self.switch_to_pydirectinput).pack(side='left', padx=5)

        # 权限状态
        admin_frame = ttk.LabelFrame(settings_frame, text="权限状态", padding=10)
        admin_frame.pack(fill='x', padx=10, pady=5)

        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if is_admin:
                status_text = "✓ 当前以管理员身份运行（全屏游戏快捷键可用）"
                status_color = "green"
            else:
                status_text = "⚠ 当前未以管理员身份运行（全屏游戏快捷键可能失效）"
                status_color = "orange"
        except:
            status_text = "? 无法检测管理员权限"
            status_color = "gray"

        admin_label = ttk.Label(admin_frame, text=status_text, foreground=status_color)
        admin_label.pack(anchor='w')

        # 热键状态
        hotkey_frame = ttk.LabelFrame(settings_frame, text="热键状态", padding=10)
        hotkey_frame.pack(fill='x', padx=10, pady=5)

        if PYNPUT_AVAILABLE and self.hotkey_listener and self.hotkey_listener.is_alive():
            hotkey_status = "✓ pynput 全局热键监听器已启用 - 全屏游戏兼容"
            hotkey_color = "green"
        else:
            hotkey_status = "✗ 热键功能不可用 - 请确保 pynput 已安装并以管理员运行"
            hotkey_color = "red"

        hotkey_label = ttk.Label(hotkey_frame, text=hotkey_status, foreground=hotkey_color)
        hotkey_label.pack(anchor='w')

        # 录制功能状态
        recording_frame = ttk.LabelFrame(settings_frame, text="录制功能状态", padding=10)
        recording_frame.pack(fill='x', padx=10, pady=5)

        if PYNPUT_AVAILABLE:
            recording_status = "✓ pynput 库已安装 - 录制功能可用"
            recording_color = "green"
        else:
            recording_status = "✗ pynput 库未安装 - 录制功能不可用"
            recording_color = "red"

        recording_label = ttk.Label(recording_frame, text=recording_status, foreground=recording_color)
        recording_label.pack(anchor='w')

        # 后台控制
        background_frame = ttk.LabelFrame(settings_frame, text="后台控制", padding=10)
        background_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(background_frame, text="最小化到系统托盘", 
                command=self.minimize_to_tray).pack(side='left', padx=5)
        ttk.Button(background_frame, text="显示/隐藏窗口 (Ctrl+Shift+H)", 
                command=self.toggle_window_visibility).pack(side='left', padx=5)

        # 快捷键说明
        shortcut_frame = ttk.LabelFrame(settings_frame, text="全局快捷键说明", padding=10)
        shortcut_frame.pack(fill='x', padx=10, pady=5)

        shortcut_text = """全局快捷键（即使窗口最小化或隐藏也能工作）：
        - Ctrl+Shift+P: 获取当前鼠标位置
        - Ctrl+Shift+W: 检测当前窗口
        - F1: 暂停/恢复当前执行的任务
        - F2: 开始执行任务（全屏游戏推荐）
        - F3: 停止执行任务（全屏游戏推荐）
        - F8: 开始录制鼠标键盘操作
        - F9: 停止录制
        - Ctrl+Shift+H: 显示/隐藏主窗口

        重要提示：
        1. 请确保以管理员身份运行本程序
        2. 部分防病毒软件可能阻止键盘钩子
        3. 在全屏游戏中，确保游戏不是"独占全屏"模式
        """

        # 使用 Text 组件，以支持滚动
        shortcut_text_widget = tk.Text(shortcut_frame, wrap="word", height=10, width=60)
        shortcut_text_widget.insert("1.0", shortcut_text)
        shortcut_text_widget.configure(state="disabled", bg=self.window.cget('bg'))
        shortcut_text_widget.pack(fill="both", expand=True)

        # 功能说明
        new_features_frame = ttk.LabelFrame(settings_frame, text="功能说明 v1.0", padding=10)
        new_features_frame.pack(fill='x', padx=10, pady=5)

        new_features_text = """功能 v1.0：
        1. pynput 集成：支持全局鼠标/键盘事件监听
        2. 动作录制功能：可录制操作并自动生成脚本
        3. 智能文本识别：自动合并连续按键为文本输入
        4. 双击自动识别：自动识别快速连续点击为双击
        5. 录制状态显示：实时显示录制状态和统计
        6. 优化键盘输入：使用直接文本输入，提高兼容性
        7. 热键扩展：F8/F9 录制控制热键
        8. 鼠标长按功能：支持鼠标长按和松开操作
        9. 窗口检测热键：Ctrl+Shift+W 快速检测当前窗口

        录制功能特点：
        - 支持录制鼠标移动、点击、滚动
        - 支持录制键盘按键和文本输入
        - 自动识别并合并连续文本输入
        - 录制期间程序后台运行
        - 录制结果可直接保存和执行
        """

        # 使用 Text 组件
        new_features_text_widget = tk.Text(new_features_frame, wrap="word", height=12, width=60)
        new_features_text_widget.insert("1.0", new_features_text)
        new_features_text_widget.configure(state="disabled", bg=self.window.cget('bg'))
        new_features_text_widget.pack(fill="both", expand=True)

        # 安全设置
        safety_frame = ttk.LabelFrame(settings_frame, text="安全设置", padding=10)
        safety_frame.pack(fill='x', padx=10, pady=5)

        self.safety_var = tk.BooleanVar(value=self.config.get('safety_enabled', True))
        ttk.Checkbutton(safety_frame, text="启用故障安全功能（移动鼠标到屏幕左上角停止程序）", 
                    variable=self.safety_var, 
                    command=self.toggle_safety).pack(anchor='w')

        ttk.Label(safety_frame, 
                text="注意：启用后，将鼠标快速移动到屏幕左上角 (0,0) 可以紧急停止程序",
                foreground='gray').pack(anchor='w', pady=5)

        # 安装提示
        install_frame = ttk.LabelFrame(settings_frame, text="依赖库安装", padding=10)
        install_frame.pack(fill='x', padx=10, pady=5)

        install_text = """如果功能不可用，请以管理员身份运行以下命令：

        命令提示符（管理员）：
        pip install pyautogui pystray pillow pydirectinput pynput

        或者使用清华镜像源加速：
        pip install pyautogui pystray pillow pydirectinput pynput -i https://pypi.tuna.tsinghua.edu.cn/simple

        注意：
        1. pydirectinput 是专门为游戏优化的库，可绕过 DirectX 输入限制
        2. pynput 库用于事件监听、录制和全局热键功能
        3. 安装后可能需要重启程序
        """

        # 使用 Text 组件
        install_text_widget = tk.Text(install_frame, wrap="word", height=10, width=60)
        install_text_widget.insert("1.0", install_text)
        install_text_widget.configure(state="disabled", bg=self.window.cget('bg'))
        install_text_widget.pack(fill="both", expand=True)

        # 添加一个底部标签，提示可以滚动
        bottom_label = ttk.Label(settings_frame, text="↑ 可以滚动查看更多内容 ↑", foreground="gray")
        bottom_label.pack(pady=10)

    def switch_to_pydirectinput(self):
        """切换到 pydirectinput 引擎"""
        if not PYDIRECTINPUT_AVAILABLE:
            messagebox.showerror("错误", "pydirectinput 库未安装，无法切换")
            return

        self.autoclicker.use_pydirectinput = True
        self.config['use_pydirectinput'] = True
        self.save_config()

        # 更新窗口标题
        self.window.title(f"鼠标键盘自动化控制 v1.0（引擎：pydirectinput）")

        messagebox.showinfo("引擎切换", "已切换到 pydirectinput 引擎（全屏游戏优化）")

    def switch_to_pyautogui(self):
        """切换到 pyautogui 引擎"""
        self.autoclicker.use_pydirectinput = False
        self.config['use_pydirectinput'] = False
        self.save_config()

        # 更新窗口标题
        self.window.title(f"鼠标键盘自动化控制 v1.0（引擎：pyautogui）")

        messagebox.showinfo("引擎切换", "已切换到 pyautogui 引擎（标准模式）")

    # ============================================================================
    # 功能函数
    # ============================================================================

    def show_context_menu(self, event):
        """显示右键菜单"""
        try:
            # 选择被点击的项目
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"显示右键菜单出错：{e}")

    def get_selected_index(self):
        """获取选中项的索引"""
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0])['values']
            index = int(item_values[0]) - 1  # 转换为 0 基索引
            return index
        return None

    def insert_move_above(self):
        """在选中项上方插入移动指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return

        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
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

        key = simpledialog.askstring("按键", "请输入按键名称（如：a, enter, space 等）:")
        if key:
            self.autoclicker.insert_action_at(index, 'press', key=key)
            self.update_action_list()
            messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入按键指令")

    def insert_drag_above(self):
        """在选中项上方插入拖拽指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return

        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
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
            messagebox.showerror("错误", f"插入滚动指令时出错：{e}")

    def insert_mousedown_above(self):
        """在选中项上方插入鼠标长按指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return

        button = simpledialog.askstring("按钮", "请输入按钮类型（left, right, middle）:", initialvalue="left")
        if button and button in ['left', 'right', 'middle']:
            self.autoclicker.insert_action_at(index, 'mousedown', button=button)
            self.update_action_list()
            messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入鼠标{button}键长按指令")
        else:
            messagebox.showerror("错误", "请输入有效的按钮类型（left, right, middle）")

    def insert_mouseup_above(self):
        """在选中项上方插入鼠标松开指令"""
        index = self.get_selected_index()
        if index is None:
            messagebox.showwarning("警告", "请先选择一个动作")
            return

        button = simpledialog.askstring("按钮", "请输入按钮类型（left, right, middle）:", initialvalue="left")
        if button and button in ['left', 'right', 'middle']:
            self.autoclicker.insert_action_at(index, 'mouseup', button=button)
            self.update_action_list()
            messagebox.showinfo("成功", f"已在第 {index+1} 个位置插入鼠标{button}键松开指令")
        else:
            messagebox.showerror("错误", "请输入有效的按钮类型（left, right, middle）")

    # ============================================================================
    # 原始功能函数
    # ============================================================================

    def get_current_pos(self):
        pos = self.autoclicker.get_current_position()
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, str(pos.x))
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, str(pos.y))
        messagebox.showinfo("当前位置", f"当前鼠标位置：X={pos.x}, Y={pos.y}")

    def move_to_pos(self):
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
            self.autoclicker.move_mouse(x, y)
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字")

    def type_text(self):
        text = self.text_entry.get()
        if text:
            self.autoclicker.type_text(text)
            self.text_entry.delete(0, tk.END)

    def add_move_action(self):
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
            action = self.autoclicker.add_action('move', x=x, y=y)
            self.update_action_list()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的坐标数字")

    def add_click_action(self, button_type='left'):
        """添加点击动作，区分左右键"""
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
        key = simpledialog.askstring("按键", "请输入按键名称（如：a, enter, space 等）:")
        if key:
            action = self.autoclicker.add_action('press', key=key)
            self.update_action_list()

    def add_drag_action(self):
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
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
            messagebox.showerror("错误", f"添加滚动动作时出错：{e}")

    def add_mousedown_action(self):
        """添加鼠标长按动作"""
        button = simpledialog.askstring("按钮", "请输入按钮类型（left, right, middle）:", initialvalue="left")
        if button and button in ['left', 'right', 'middle']:
            action = self.autoclicker.add_action('mousedown', button=button)
            self.update_action_list()
            messagebox.showinfo("成功", f"已添加鼠标{button}键长按动作")
        else:
            messagebox.showerror("错误", "请输入有效的按钮类型（left, right, middle）")

    def add_mouseup_action(self):
        """添加鼠标松开动作"""
        button = simpledialog.askstring("按钮", "请输入按钮类型（left, right, middle）:", initialvalue="left")
        if button and button in ['left', 'right', 'middle']:
            action = self.autoclicker.add_action('mouseup', button=button)
            self.update_action_list()
            messagebox.showinfo("成功", f"已添加鼠标{button}键松开动作")
        else:
            messagebox.showerror("错误", "请输入有效的按钮类型（left, right, middle）")

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
            recorded = "✓" if action.get('recorded', False) else ""

            self.tree.insert('', 'end', values=(i+1, action_type, params_str, recorded, timestamp))

    def start_sequence(self):
        try:
            repeat = int(self.repeat_var.get())
            interval = float(self.interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "请检查重复次数和间隔时间的数值")
            return

        target_window = self.target_window_var.get().strip()
        if target_window:
            print(f"将只在包含 '{target_window}' 的窗口中执行")

        def run_in_thread():
            self.autoclicker.run_actions(repeat=repeat, interval=interval, target_window=target_window)

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
            self.config['safety_enabled'] = True
        else:
            pyautogui.FAILSAFE = False
            self.config['safety_enabled'] = False
        self.save_config()

    def cleanup(self):
        """清理资源"""
        try:
            # 停止热键监听器
            if self.hotkey_listener:
                self.hotkey_listener.stop()
                print("pynput 热键监听器已停止")

            # 停止录制（如果正在录制）
            if self.autoclicker.recording:
                self.autoclicker.stop_recording()
        except Exception as e:
            print(f"停止热键管理器时出错：{e}")

    def run(self):
        """启动 GUI"""
        self.window.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.window.mainloop()

# ============================================================================
# 主程序入口
# ============================================================================

def check_dependencies():
    """检查依赖库"""
    print("=" * 60)
    print("自动化脚本 v1.0 (纯 pynput 版)")
    print("=" * 60)

    core_missing = []
    optional_missing = []

    # 检查核心库
    try:
        import pyautogui
        print("✓ pyautogui")
    except ImportError:
        core_missing.append("pyautogui")
        print("✗ pyautogui")

    # 检查游戏优化库
    try:
        import pydirectinput
        print("✓ pydirectinput（游戏优化）")
    except ImportError:
        optional_missing.append("pydirectinput")
        print("✗ pydirectinput（游戏优化）")

    # 检查录制库 (核心依赖)
    try:
        from pynput import mouse, keyboard
        print("✓ pynput（录制功能 & 全局热键）")
    except ImportError:
        core_missing.append("pynput")  # pynput 现在是核心依赖
        print("✗ pynput（录制功能 & 全局热键）")

    # 检查可选库
    try:
        import pystray
        from PIL import Image
        print("✓ pystray + PIL (系统托盘)")
    except ImportError:
        optional_missing.append("pystray pillow")
        print("✗ pystray + PIL (系统托盘)")

    print("=" * 60)

    if core_missing:
        print("缺少核心依赖库，程序无法运行！")
        print("请运行以下命令安装：")
        print("pip install " + " ".join(core_missing))
        return False

    if optional_missing:
        print("缺少可选依赖库，部分功能将不可用：")
        print("缺少的库：" + ", ".join(optional_missing))
        print("\n安装命令：")
        print("pip install " + " ".join(optional_missing))

        if "pydirectinput" in optional_missing:
            print("注意：pydirectinput 是游戏优化库，安装后可获得更好的全屏游戏兼容性")

        response = messagebox.askyesno("可选依赖库缺失", 
            f"缺少以下可选依赖库：{', '.join(optional_missing)}\n\n"
            "部分功能将不可用。是否立即安装？\n\n"
            "注意：需要管理员权限。")

        if response:
            try:
                import subprocess
                subprocess.run(f"pip install {' '.join(optional_missing)} -i https://pypi.tuna.tsinghua.edu.cn/simple", 
                             shell=True, check=True)
                print("可选依赖库安装完成！")
                messagebox.showinfo("安装成功", "可选依赖库安装完成！\n请重启程序以使用全部功能。")
            except Exception as e:
                print(f"安装可选依赖库失败：{e}")
                messagebox.showwarning("安装失败", "可选依赖库安装失败，部分功能将不可用。\n请手动安装。")

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
        print(f"程序启动失败：{e}")
        print(f"详细错误：{traceback.format_exc()}")
        messagebox.showerror("启动失败", 
            f"程序启动失败:\n\n{str(e)}\n\n"
            "请检查：\n"
            "1. 是否以管理员身份运行\n"
            "2. 依赖库是否安装完整\n"
            "3. 防病毒软件是否阻止了程序")

if __name__ == "__main__":
    main()
