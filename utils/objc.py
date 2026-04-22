"""
utils/objc.py — macOS Objective-C runtime 辅助工具

提供轻量封装，让调用方无需重复设置 argtypes/restype。
只在 macOS 上可用；所有公共函数在非 macOS 平台上会静默返回 None / 空值。
"""
import ctypes

_LIBOBJC_PATH = '/usr/lib/libobjc.dylib'


def load_objc():
    """加载 libobjc，返回 (objc, sel_fn, msg0_fn) 三元组，失败时返回 None。

    - sel_fn(name: str) -> c_void_p
    - msg0_fn(obj, sel_name: str) -> c_void_p  （无额外参数的消息）
    """
    try:
        objc = ctypes.cdll.LoadLibrary(_LIBOBJC_PATH)
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        def sel(name):
            return objc.sel_registerName(name.encode())

        def msg0(obj, sel_name):
            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            return objc.objc_msgSend(obj, sel(sel_name))

        return objc, sel, msg0
    except Exception:
        return None


def nsstring_to_py(objc, sel, nsstr):
    """将 NSString* 转为 Python str，失败时返回空字符串。"""
    if not nsstr:
        return ''
    try:
        objc.objc_msgSend.restype = ctypes.c_char_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        b = objc.objc_msgSend(nsstr, sel('UTF8String'))
        return b.decode('utf-8', errors='replace') if b else ''
    except Exception:
        return ''


def get_all_ns_windows(objc, sel, msg0):
    """返回所有 NSWindow 的列表（c_void_p）。失败时返回空列表。"""
    try:
        NSApp = msg0(objc.objc_getClass(b'NSApplication'), 'sharedApplication')
        windows = msg0(NSApp, 'windows')
        objc.objc_msgSend.restype = ctypes.c_long
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        count = objc.objc_msgSend(windows, sel('count'))
        result = []
        for i in range(count):
            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            w = objc.objc_msgSend(windows, sel('objectAtIndex:'), ctypes.c_ulong(i))
            result.append(w)
        return result
    except Exception:
        return []


def get_style_mask(objc, sel, nswin):
    """返回 NSWindow 的 styleMask（int），失败时返回 -1。"""
    try:
        objc.objc_msgSend.restype = ctypes.c_ulong
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        return objc.objc_msgSend(nswin, sel('styleMask'))
    except Exception:
        return -1


def set_window_level(objc, sel, nswin, level):
    """设置 NSWindow level（int）。"""
    objc.objc_msgSend.restype = None
    objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
    objc.objc_msgSend(nswin, sel('setLevel:'), ctypes.c_long(level))


def set_collection_behavior(objc, sel, nswin, behavior):
    """设置 NSWindow collectionBehavior（int）。"""
    objc.objc_msgSend.restype = None
    objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    objc.objc_msgSend(nswin, sel('setCollectionBehavior:'), ctypes.c_ulong(behavior))


def find_ns_window_by_title(objc, sel, msg0, title):
    """按标题查找 NSWindow，返回第一个匹配的 c_void_p，找不到返回 None。"""
    for w in get_all_ns_windows(objc, sel, msg0):
        if nsstring_to_py(objc, sel, msg0(w, 'title')) == title:
            return w
    return None
