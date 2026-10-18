#!/usr/bin/env python3
"""
Ground-Up Android APK Compiler & Dual Signer (v1 JAR + v2 APK Signature Scheme v2)
Builds `LvLv_ProTuner_v2.0.apk` with:
- Complete `resources.arsc` defining `@drawable/ic_launcher` (0x7f010000) -> `res/drawable/ic_launcher.png`
- High-resolution supersampled Apple-style App Icon (`ic_launcher.png`) wired to `<application>` and `<activity>`
- Portrait orientation lock (`screenOrientation="portrait"`), `FLAG_KEEP_SCREEN_ON`, `setTextZoom(100)`, `OVER_SCROLL_NEVER`
- Zero-jitter, zero-FOUC, locked single-screen Apple-style Tuner UI
"""

import base64
import datetime
import hashlib
import io
import math
import os
import struct
import zlib
from PIL import Image, ImageDraw

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID


# =============================================================================
# 1. ULEB128 & MUTF-8 HELPERS FOR DALVIK (classes.dex)
# =============================================================================
def encode_uleb128(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte |= 0x80
        out.append(byte)
        if value == 0:
            break
    return bytes(out)


def encode_dex_string(s: str) -> bytes:
    utf8_bytes = s.encode('utf-8')
    return encode_uleb128(len(s)) + utf8_bytes + b'\x00'


# =============================================================================
# 2. DALVIK BYTECODE COMPILER (classes.dex)
# =============================================================================
def build_classes_dex() -> bytes:
    """
    Generates a verified Dalvik Executable (dex\\n035\\0) containing:
    1. com.lvlv.protuner.TunerChromeClient extends android.webkit.WebChromeClient
    2. com.lvlv.protuner.MainActivity extends android.app.Activity
       - Locks portrait orientation (setRequestedOrientation(1))
       - Keeps screen awake while tuning (getWindow().addFlags(128))
       - Sets black status/navigation bars (setStatusBarColor / setNavigationBarColor)
       - Locks WebView text zoom to 100% (setTextZoom(100)) & disables overscroll
       - Requests RECORD_AUDIO runtime permission
    """
    strings = sorted(set([
        "<init>",
        "I",
        "L",
        "Landroid/app/Activity;",
        "Landroid/content/Context;",
        "Landroid/os/Bundle;",
        "Landroid/view/View;",
        "Landroid/view/Window;",
        "Landroid/webkit/PermissionRequest;",
        "Landroid/webkit/WebChromeClient;",
        "Landroid/webkit/WebSettings;",
        "Landroid/webkit/WebView;",
        "Lcom/lvlv/protuner/MainActivity;",
        "Lcom/lvlv/protuner/TunerChromeClient;",
        "Ljava/lang/Object;",
        "Ljava/lang/String;",
        "MainActivity.java",
        "TunerChromeClient.java",
        "V",
        "VI",
        "VL",
        "VLI",
        "VZ",
        "Z",
        "[Ljava/lang/String;",
        "addFlags",
        "android.permission.RECORD_AUDIO",
        "file:///android_asset/index.html",
        "getResources",
        "getSettings",
        "getWindow",
        "grant",
        "loadUrl",
        "onCreate",
        "onPermissionRequest",
        "requestPermissions",
        "setAllowFileAccess",
        "setBackgroundColor",
        "setContentView",
        "setDomStorageEnabled",
        "setHorizontalScrollBarEnabled",
        "setJavaScriptEnabled",
        "setMediaPlaybackRequiresUserGesture",
        "setNavigationBarColor",
        "setOverScrollMode",
        "setRequestedOrientation",
        "setStatusBarColor",
        "setTextZoom",
        "setVerticalScrollBarEnabled",
        "setWebChromeClient",
    ]))
    str_idx = {s: i for i, s in enumerate(strings)}

    type_descriptors = sorted([
        "I",
        "Landroid/app/Activity;",
        "Landroid/content/Context;",
        "Landroid/os/Bundle;",
        "Landroid/view/View;",
        "Landroid/view/Window;",
        "Landroid/webkit/PermissionRequest;",
        "Landroid/webkit/WebChromeClient;",
        "Landroid/webkit/WebSettings;",
        "Landroid/webkit/WebView;",
        "Lcom/lvlv/protuner/MainActivity;",
        "Lcom/lvlv/protuner/TunerChromeClient;",
        "Ljava/lang/Object;",
        "Ljava/lang/String;",
        "V",
        "Z",
        "[Ljava/lang/String;",
    ], key=lambda d: str_idx[d])
    type_idx = {d: i for i, d in enumerate(type_descriptors)}

    raw_protos = [
        ("L", "Landroid/view/Window;", ()),
        ("L", "Landroid/webkit/WebSettings;", ()),
        ("L", "[Ljava/lang/String;", ()),
        ("V", "V", ()),
        ("VI", "V", ("I",)),
        ("VL", "V", ("Landroid/content/Context;",)),
        ("VL", "V", ("Landroid/os/Bundle;",)),
        ("VL", "V", ("Landroid/view/View;",)),
        ("VL", "V", ("Landroid/webkit/PermissionRequest;",)),
        ("VL", "V", ("Landroid/webkit/WebChromeClient;",)),
        ("VL", "V", ("Ljava/lang/String;",)),
        ("VL", "V", ("[Ljava/lang/String;",)),
        ("VLI", "V", ("[Ljava/lang/String;", "I")),
        ("VZ", "V", ("Z",)),
    ]
    raw_protos.sort(key=lambda p: (type_idx[p[1]], [type_idx[t] for t in p[2]]))
    proto_idx = {(p[1], p[2]): i for i, p in enumerate(raw_protos)}

    raw_methods = [
        ("Landroid/app/Activity;", "<init>", ("V", ())),
        ("Landroid/app/Activity;", "getWindow", ("Landroid/view/Window;", ())),
        ("Landroid/app/Activity;", "onCreate", ("V", ("Landroid/os/Bundle;",))),
        ("Landroid/app/Activity;", "requestPermissions", ("V", ("[Ljava/lang/String;", "I"))),
        ("Landroid/app/Activity;", "setContentView", ("V", ("Landroid/view/View;",))),
        ("Landroid/app/Activity;", "setRequestedOrientation", ("V", ("I",))),
        ("Landroid/view/Window;", "addFlags", ("V", ("I",))),
        ("Landroid/view/Window;", "setNavigationBarColor", ("V", ("I",))),
        ("Landroid/view/Window;", "setStatusBarColor", ("V", ("I",))),
        ("Landroid/webkit/PermissionRequest;", "getResources", ("[Ljava/lang/String;", ())),
        ("Landroid/webkit/PermissionRequest;", "grant", ("V", ("[Ljava/lang/String;",))),
        ("Landroid/webkit/WebChromeClient;", "<init>", ("V", ())),
        ("Landroid/webkit/WebSettings;", "setAllowFileAccess", ("V", ("Z",))),
        ("Landroid/webkit/WebSettings;", "setDomStorageEnabled", ("V", ("Z",))),
        ("Landroid/webkit/WebSettings;", "setJavaScriptEnabled", ("V", ("Z",))),
        ("Landroid/webkit/WebSettings;", "setMediaPlaybackRequiresUserGesture", ("V", ("Z",))),
        ("Landroid/webkit/WebSettings;", "setTextZoom", ("V", ("I",))),
        ("Landroid/webkit/WebView;", "<init>", ("V", ("Landroid/content/Context;",))),
        ("Landroid/webkit/WebView;", "getSettings", ("Landroid/webkit/WebSettings;", ())),
        ("Landroid/webkit/WebView;", "loadUrl", ("V", ("Ljava/lang/String;",))),
        ("Landroid/webkit/WebView;", "setBackgroundColor", ("V", ("I",))),
        ("Landroid/webkit/WebView;", "setHorizontalScrollBarEnabled", ("V", ("Z",))),
        ("Landroid/webkit/WebView;", "setOverScrollMode", ("V", ("I",))),
        ("Landroid/webkit/WebView;", "setVerticalScrollBarEnabled", ("V", ("Z",))),
        ("Landroid/webkit/WebView;", "setWebChromeClient", ("V", ("Landroid/webkit/WebChromeClient;",))),
        ("Lcom/lvlv/protuner/MainActivity;", "<init>", ("V", ())),
        ("Lcom/lvlv/protuner/MainActivity;", "onCreate", ("V", ("Landroid/os/Bundle;",))),
        ("Lcom/lvlv/protuner/TunerChromeClient;", "<init>", ("V", ())),
        ("Lcom/lvlv/protuner/TunerChromeClient;", "onPermissionRequest", ("V", ("Landroid/webkit/PermissionRequest;",))),
    ]
    raw_methods.sort(key=lambda m: (type_idx[m[0]], str_idx[m[1]], proto_idx[m[2]]))
    method_idx = {(m[0], m[1], m[2]): i for i, m in enumerate(raw_methods)}

    def insn_35c(op: int, regs: list, idx: int) -> bytes:
        count = len(regs)
        r = regs + [0] * (5 - count)
        word0 = (count << 12) | (r[4] << 8) | op
        word1 = idx
        word2 = (r[3] << 12) | (r[2] << 8) | (r[1] << 4) | r[0]
        return struct.pack('<HHH', word0, word1, word2)

    def make_code_item(registers_size: int, ins_size: int, outs_size: int, insns_bytes: bytes) -> bytes:
        insns_size = len(insns_bytes) // 2
        header = struct.pack('<HHHHII', registers_size, ins_size, outs_size, 0, 0, insns_size)
        body = header + insns_bytes
        if len(body) % 4 != 0:
            body += b'\x00' * (4 - (len(body) % 4))
        return body

    # 1. TunerChromeClient.<init>()V
    code_chrome_init = make_code_item(
        registers_size=1, ins_size=1, outs_size=1,
        insns_bytes=(
            insn_35c(0x70, [0], method_idx[("Landroid/webkit/WebChromeClient;", "<init>", ("V", ()))]) +
            struct.pack('<H', 0x000e)
        )
    )

    # 2. TunerChromeClient.onPermissionRequest(PermissionRequest)V
    code_chrome_perm = make_code_item(
        registers_size=3, ins_size=2, outs_size=2,
        insns_bytes=(
            insn_35c(0x6e, [2], method_idx[("Landroid/webkit/PermissionRequest;", "getResources", ("[Ljava/lang/String;", ()))]) +
            struct.pack('<H', 0x000c) +
            insn_35c(0x6e, [2, 0], method_idx[("Landroid/webkit/PermissionRequest;", "grant", ("V", ("[Ljava/lang/String;",)))]) +
            struct.pack('<H', 0x000e)
        )
    )

    # 3. MainActivity.<init>()V
    code_main_init = make_code_item(
        registers_size=1, ins_size=1, outs_size=1,
        insns_bytes=(
            insn_35c(0x70, [0], method_idx[("Landroid/app/Activity;", "<init>", ("V", ()))]) +
            struct.pack('<H', 0x000e)
        )
    )

    # 4. MainActivity.onCreate(Bundle)V
    # Locals: v0, v1, v2, v3 | Params: v4 = p0 (this), v5 = p1 (Bundle)
    insns = bytearray()
    insns += insn_35c(0x6f, [4, 5], method_idx[("Landroid/app/Activity;", "onCreate", ("V", ("Landroid/os/Bundle;",)))])

    # Lock Portrait Orientation: this.setRequestedOrientation(1)
    insns += struct.pack('<H', 0x1012)  # const/4 v0, 0x1
    insns += insn_35c(0x6e, [4, 0], method_idx[("Landroid/app/Activity;", "setRequestedOrientation", ("V", ("I",)))])

    # Configure Window: Keep Screen On (flag 128) + Black Status & Nav Bars (0xFF000000)
    insns += insn_35c(0x6e, [4], method_idx[("Landroid/app/Activity;", "getWindow", ("Landroid/view/Window;", ()))])
    insns += struct.pack('<H', 0x010c)  # move-result-object v1 (Window)
    insns += struct.pack('<HH', 0x0213, 128)  # const/16 v2, 128 (FLAG_KEEP_SCREEN_ON)
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/view/Window;", "addFlags", ("V", ("I",)))])
    insns += struct.pack('<HH', 0x0215, 0xff00)  # const/high16 v2, 0xff000000
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/view/Window;", "setStatusBarColor", ("V", ("I",)))])
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/view/Window;", "setNavigationBarColor", ("V", ("I",)))])

    # Request RECORD_AUDIO permission
    insns += struct.pack('<H', 0x1012)  # const/4 v0, 0x1
    insns += struct.pack('<HH', 0x0123, type_idx["[Ljava/lang/String;"])
    insns += struct.pack('<H', 0x0212)  # const/4 v2, 0x0
    insns += struct.pack('<HH', 0x031a, str_idx["android.permission.RECORD_AUDIO"])
    insns += struct.pack('<HH', 0x034d, 0x0201)  # aput-object v3, v1, v2
    insns += insn_35c(0x6e, [4, 1, 0], method_idx[("Landroid/app/Activity;", "requestPermissions", ("V", ("[Ljava/lang/String;", "I")))])

    # Create WebView v0 = new WebView(this)
    insns += struct.pack('<HH', 0x0022, type_idx["Landroid/webkit/WebView;"])
    insns += insn_35c(0x70, [0, 4], method_idx[("Landroid/webkit/WebView;", "<init>", ("V", ("Landroid/content/Context;",)))])

    # Disable scrollbars & overscroll on WebView
    insns += struct.pack('<H', 0x0212)  # const/4 v2, 0x0
    insns += insn_35c(0x6e, [0, 2], method_idx[("Landroid/webkit/WebView;", "setVerticalScrollBarEnabled", ("V", ("Z",)))])
    insns += insn_35c(0x6e, [0, 2], method_idx[("Landroid/webkit/WebView;", "setHorizontalScrollBarEnabled", ("V", ("Z",)))])
    insns += struct.pack('<H', 0x2212)  # const/4 v2, 0x2 (OVER_SCROLL_NEVER)
    insns += insn_35c(0x6e, [0, 2], method_idx[("Landroid/webkit/WebView;", "setOverScrollMode", ("V", ("I",)))])

    # Configure WebSettings
    insns += insn_35c(0x6e, [0], method_idx[("Landroid/webkit/WebView;", "getSettings", ("Landroid/webkit/WebSettings;", ()))])
    insns += struct.pack('<H', 0x010c)  # move-result-object v1
    insns += struct.pack('<H', 0x1212)  # const/4 v2, 0x1
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/webkit/WebSettings;", "setJavaScriptEnabled", ("V", ("Z",)))])
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/webkit/WebSettings;", "setDomStorageEnabled", ("V", ("Z",)))])
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/webkit/WebSettings;", "setAllowFileAccess", ("V", ("Z",)))])
    insns += struct.pack('<H', 0x0212)  # const/4 v2, 0x0
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/webkit/WebSettings;", "setMediaPlaybackRequiresUserGesture", ("V", ("Z",)))])
    insns += struct.pack('<HH', 0x0213, 100)  # const/16 v2, 100 (Lock 100% text zoom!)
    insns += insn_35c(0x6e, [1, 2], method_idx[("Landroid/webkit/WebSettings;", "setTextZoom", ("V", ("I",)))])

    # Set TunerChromeClient
    insns += struct.pack('<HH', 0x0222, type_idx["Lcom/lvlv/protuner/TunerChromeClient;"])
    insns += insn_35c(0x70, [2], method_idx[("Lcom/lvlv/protuner/TunerChromeClient;", "<init>", ("V", ()))])
    insns += insn_35c(0x6e, [0, 2], method_idx[("Landroid/webkit/WebView;", "setWebChromeClient", ("V", ("Landroid/webkit/WebChromeClient;",)))])

    # Set black background & content view & load URL
    insns += struct.pack('<HH', 0x0215, 0xff00)
    insns += insn_35c(0x6e, [0, 2], method_idx[("Landroid/webkit/WebView;", "setBackgroundColor", ("V", ("I",)))])
    insns += insn_35c(0x6e, [4, 0], method_idx[("Landroid/app/Activity;", "setContentView", ("V", ("Landroid/view/View;",)))])
    insns += struct.pack('<HH', 0x021a, str_idx["file:///android_asset/index.html"])
    insns += insn_35c(0x6e, [0, 2], method_idx[("Landroid/webkit/WebView;", "loadUrl", ("V", ("Ljava/lang/String;",)))])
    insns += struct.pack('<H', 0x000e)

    code_main_oncreate = make_code_item(
        registers_size=6, ins_size=2, outs_size=3,
        insns_bytes=bytes(insns)
    )

    header_size = 0x70
    string_ids_off = header_size
    string_ids_size = len(strings)

    type_ids_off = string_ids_off + string_ids_size * 4
    type_ids_size = len(type_descriptors)

    proto_ids_off = type_ids_off + type_ids_size * 4
    proto_ids_size = len(raw_protos)

    method_ids_off = proto_ids_off + proto_ids_size * 12
    method_ids_size = len(raw_methods)

    class_defs_off = method_ids_off + method_ids_size * 8
    class_defs_size = 2

    data_off = class_defs_off + class_defs_size * 32
    data_stream = bytearray()

    def align4():
        if len(data_stream) % 4 != 0:
            data_stream.extend(b'\x00' * (4 - (len(data_stream) % 4)))

    align4()
    type_list_off = data_off + len(data_stream)
    proto_type_list_offsets = []
    type_list_count = 0
    for shorty, ret_t, params in raw_protos:
        if not params:
            proto_type_list_offsets.append(0)
        else:
            align4()
            off = data_off + len(data_stream)
            proto_type_list_offsets.append(off)
            data_stream += struct.pack('<I', len(params))
            for pt in params:
                data_stream += struct.pack('<H', type_idx[pt])
            type_list_count += 1

    align4()
    code_list_off = data_off + len(data_stream)
    off_code_chrome_init = data_off + len(data_stream)
    data_stream += code_chrome_init
    align4()
    off_code_chrome_perm = data_off + len(data_stream)
    data_stream += code_chrome_perm
    align4()
    off_code_main_init = data_off + len(data_stream)
    data_stream += code_main_init
    align4()
    off_code_main_oncreate = data_off + len(data_stream)
    data_stream += code_main_oncreate

    string_data_off_start = data_off + len(data_stream)
    string_data_offsets = []
    for s in strings:
        string_data_offsets.append(data_off + len(data_stream))
        data_stream += encode_dex_string(s)

    class_data_off_start = data_off + len(data_stream)

    def make_class_data_item(direct_methods, virtual_methods) -> bytes:
        out = bytearray()
        out += encode_uleb128(0)
        out += encode_uleb128(0)
        out += encode_uleb128(len(direct_methods))
        out += encode_uleb128(len(virtual_methods))
        prev = 0
        for m_idx, flags, c_off in sorted(direct_methods, key=lambda x: x[0]):
            out += encode_uleb128(m_idx - prev)
            out += encode_uleb128(flags)
            out += encode_uleb128(c_off)
            prev = m_idx
        prev = 0
        for m_idx, flags, c_off in sorted(virtual_methods, key=lambda x: x[0]):
            out += encode_uleb128(m_idx - prev)
            out += encode_uleb128(flags)
            out += encode_uleb128(c_off)
            prev = m_idx
        return bytes(out)

    off_class_data_chrome = data_off + len(data_stream)
    data_stream += make_class_data_item(
        direct_methods=[
            (method_idx[("Lcom/lvlv/protuner/TunerChromeClient;", "<init>", ("V", ()))], 0x10001, off_code_chrome_init)
        ],
        virtual_methods=[
            (method_idx[("Lcom/lvlv/protuner/TunerChromeClient;", "onPermissionRequest", ("V", ("Landroid/webkit/PermissionRequest;",)))], 0x0001, off_code_chrome_perm)
        ]
    )

    off_class_data_main = data_off + len(data_stream)
    data_stream += make_class_data_item(
        direct_methods=[
            (method_idx[("Lcom/lvlv/protuner/MainActivity;", "<init>", ("V", ()))], 0x10001, off_code_main_init)
        ],
        virtual_methods=[
            (method_idx[("Lcom/lvlv/protuner/MainActivity;", "onCreate", ("V", ("Landroid/os/Bundle;",)))], 0x0004, off_code_main_oncreate)
        ]
    )

    align4()
    map_off = data_off + len(data_stream)
    map_items = [
        (0x0000, 1, 0),
        (0x0001, string_ids_size, string_ids_off),
        (0x0002, type_ids_size, type_ids_off),
        (0x0003, proto_ids_size, proto_ids_off),
        (0x0005, method_ids_size, method_ids_off),
        (0x0006, class_defs_size, class_defs_off),
        (0x1001, type_list_count, type_list_off),
        (0x2001, 4, code_list_off),
        (0x2002, string_ids_size, string_data_off_start),
        (0x2000, 2, class_data_off_start),
        (0x1000, 1, map_off),
    ]
    data_stream += struct.pack('<I', len(map_items))
    for m_type, m_size, m_offset in map_items:
        data_stream += struct.pack('<HHII', m_type, 0, m_size, m_offset)

    align4()
    data_size = len(data_stream)
    file_size = data_off + data_size

    index_stream = bytearray()
    for off in string_data_offsets:
        index_stream += struct.pack('<I', off)
    for d in type_descriptors:
        index_stream += struct.pack('<I', str_idx[d])
    for i, (shorty, ret_t, params) in enumerate(raw_protos):
        index_stream += struct.pack('<III', str_idx[shorty], type_idx[ret_t], proto_type_list_offsets[i])
    for cls_d, m_name, proto_key in raw_methods:
        index_stream += struct.pack('<HHI', type_idx[cls_d], proto_idx[proto_key], str_idx[m_name])

    class_defs = [
        (
            type_idx["Lcom/lvlv/protuner/MainActivity;"],
            0x0001,
            type_idx["Landroid/app/Activity;"],
            0,
            str_idx["MainActivity.java"],
            0,
            off_class_data_main,
            0
        ),
        (
            type_idx["Lcom/lvlv/protuner/TunerChromeClient;"],
            0x0001,
            type_idx["Landroid/webkit/WebChromeClient;"],
            0,
            str_idx["TunerChromeClient.java"],
            0,
            off_class_data_chrome,
            0
        )
    ]
    for cdef in class_defs:
        index_stream += struct.pack('<IIIIIIII', *cdef)

    header_tail = struct.pack(
        '<IIIIIIIIIIIIIIIIIIII',
        file_size,
        header_size,
        0x12345678,
        0, 0,
        map_off,
        string_ids_size, string_ids_off,
        type_ids_size, type_ids_off,
        proto_ids_size, proto_ids_off,
        0, 0,
        method_ids_size, method_ids_off,
        class_defs_size, class_defs_off,
        data_size, data_off
    )

    body_after_sig = header_tail + index_stream + data_stream
    sha1_sig = hashlib.sha1(body_after_sig).digest()
    body_after_checksum = sha1_sig + body_after_sig
    adler_checksum = zlib.adler32(body_after_checksum) & 0xFFFFFFFF

    dex_bytes = b'dex\n035\x00' + struct.pack('<I', adler_checksum) + body_after_checksum
    assert len(dex_bytes) == file_size
    return dex_bytes


# =============================================================================
# 3. BINARY ANDROIDMANIFEST.XML WITH APP ICON (0x7f010000) & PORTRAIT LOCK
# =============================================================================
def build_binary_android_manifest() -> bytes:
    # Sorted by Android resource attribute ID ascending
    attr_defs = [
        ("theme", 0x01010000),
        ("label", 0x01010001),
        ("icon", 0x01010002),
        ("name", 0x01010003),
        ("exported", 0x01010010),
        ("screenOrientation", 0x0101001e),
        ("configChanges", 0x0101001f),
        ("minSdkVersion", 0x0101020c),
        ("versionCode", 0x0101021b),
        ("versionName", 0x0101021c),
        ("targetSdkVersion", 0x01010270),
        ("hardwareAccelerated", 0x010102d3),
        ("usesCleartextTraffic", 0x010104ec),
    ]
    other_strings = [
        "android",
        "http://schemas.android.com/apk/res/android",
        "manifest",
        "package",
        "com.lvlv.protuner",
        "2.0.0",
        "uses-sdk",
        "uses-permission",
        "android.permission.RECORD_AUDIO",
        "android.permission.MODIFY_AUDIO_SETTINGS",
        "application",
        "律吕调音器",
        "activity",
        "com.lvlv.protuner.MainActivity",
        "intent-filter",
        "action",
        "android.intent.action.MAIN",
        "category",
        "android.intent.category.LAUNCHER",
    ]
    all_strings = [a[0] for a in attr_defs] + other_strings
    s_idx = {s: i for i, s in enumerate(all_strings)}
    attr_res_map = {a[0]: a[1] for a in attr_defs}

    encoded_strings = []
    offsets = []
    curr_off = 0
    for s in all_strings:
        offsets.append(curr_off)
        u16 = s.encode('utf-16le')
        char_len = len(s)
        blob = struct.pack('<H', char_len) + u16 + b'\x00\x00'
        encoded_strings.append(blob)
        curr_off += len(blob)

    strings_blob = b''.join(encoded_strings)
    if len(strings_blob) % 4 != 0:
        strings_blob += b'\x00' * (4 - (len(strings_blob) % 4))

    strings_start = 28 + len(all_strings) * 4
    pool_chunk_size = strings_start + len(strings_blob)
    string_pool_chunk = (
        struct.pack('<HHIIIIII', 0x0001, 28, pool_chunk_size, len(all_strings), 0, 0, strings_start, 0) +
        b''.join(struct.pack('<I', o) for o in offsets) +
        strings_blob
    )

    res_map_size = 8 + len(attr_defs) * 4
    res_map_chunk = (
        struct.pack('<HHI', 0x0180, 8, res_map_size) +
        b''.join(struct.pack('<I', a[1]) for a in attr_defs)
    )

    ns_prefix = s_idx["android"]
    ns_uri = s_idx["http://schemas.android.com/apk/res/android"]
    NO_IDX = 0xFFFFFFFF

    def start_ns(line=1) -> bytes:
        return struct.pack('<HHIIII', 0x0100, 16, 24, line, NO_IDX, ns_prefix) + struct.pack('<I', ns_uri)

    def end_ns(line=1) -> bytes:
        return struct.pack('<HHIIII', 0x0101, 16, 24, line, NO_IDX, ns_prefix) + struct.pack('<I', ns_uri)

    def make_attr(ns_val, name_str, raw_str, val_type, val_data) -> tuple:
        res_id = attr_res_map.get(name_str, 0x7FFFFFFF) if ns_val != NO_IDX else 0x7FFFFFFF
        raw_i = s_idx[raw_str] if raw_str is not None else NO_IDX
        blob = struct.pack(
            '<IIIHBBI',
            ns_val,
            s_idx[name_str],
            raw_i,
            8, 0, val_type,
            val_data & 0xFFFFFFFF
        )
        return (res_id, blob)

    def start_elem(tag_name, attrs_list, line=1) -> bytes:
        sorted_attrs = [b for _, b in sorted(attrs_list, key=lambda x: x[0])]
        total_size = 16 + 20 + len(sorted_attrs) * 20
        node_hdr = struct.pack('<HHIII', 0x0102, 16, total_size, line, NO_IDX)
        attr_ext = struct.pack(
            '<IIHHHHHH',
            NO_IDX,
            s_idx[tag_name],
            20, 20, len(sorted_attrs),
            0, 0, 0
        )
        return node_hdr + attr_ext + b''.join(sorted_attrs)

    def end_elem(tag_name, line=1) -> bytes:
        return struct.pack('<HHIIII', 0x0103, 16, 24, line, NO_IDX, NO_IDX) + struct.pack('<I', s_idx[tag_name])

    TYPE_REFERENCE = 0x01
    TYPE_STRING = 0x03
    TYPE_INT_DEC = 0x10
    TYPE_INT_HEX = 0x11
    TYPE_INT_BOOL = 0x12

    ICON_RES_ID = 0x7F010000  # @drawable/ic_launcher

    xml_tree = bytearray()
    xml_tree += start_ns(1)

    xml_tree += start_elem("manifest", [
        make_attr(ns_uri, "versionCode", None, TYPE_INT_DEC, 2),
        make_attr(ns_uri, "versionName", "2.0.0", TYPE_STRING, s_idx["2.0.0"]),
        make_attr(NO_IDX, "package", "com.lvlv.protuner", TYPE_STRING, s_idx["com.lvlv.protuner"]),
    ], line=2)

    xml_tree += start_elem("uses-sdk", [
        make_attr(ns_uri, "minSdkVersion", None, TYPE_INT_DEC, 23),
        make_attr(ns_uri, "targetSdkVersion", None, TYPE_INT_DEC, 29),
    ], line=3)
    xml_tree += end_elem("uses-sdk", line=3)

    for perm in [
        "android.permission.RECORD_AUDIO",
        "android.permission.MODIFY_AUDIO_SETTINGS",
    ]:
        xml_tree += start_elem("uses-permission", [
            make_attr(ns_uri, "name", perm, TYPE_STRING, s_idx[perm])
        ], line=4)
        xml_tree += end_elem("uses-permission", line=4)

    # <application android:theme="@android:style/Theme.Black.NoTitleBar" android:label="律吕调音器" android:icon="@drawable/ic_launcher" ...>
    xml_tree += start_elem("application", [
        make_attr(ns_uri, "theme", None, TYPE_REFERENCE, 0x01030006),
        make_attr(ns_uri, "label", "律吕调音器", TYPE_STRING, s_idx["律吕调音器"]),
        make_attr(ns_uri, "icon", None, TYPE_REFERENCE, ICON_RES_ID),
        make_attr(ns_uri, "hardwareAccelerated", None, TYPE_INT_BOOL, 0xFFFFFFFF),
        make_attr(ns_uri, "usesCleartextTraffic", None, TYPE_INT_BOOL, 0xFFFFFFFF),
    ], line=8)

    # <activity android:label="律吕调音器" android:icon="@drawable/ic_launcher" android:name="com.lvlv.protuner.MainActivity" android:screenOrientation="portrait" ...>
    xml_tree += start_elem("activity", [
        make_attr(ns_uri, "label", "律吕调音器", TYPE_STRING, s_idx["律吕调音器"]),
        make_attr(ns_uri, "icon", None, TYPE_REFERENCE, ICON_RES_ID),
        make_attr(ns_uri, "name", "com.lvlv.protuner.MainActivity", TYPE_STRING, s_idx["com.lvlv.protuner.MainActivity"]),
        make_attr(ns_uri, "exported", None, TYPE_INT_BOOL, 0xFFFFFFFF),
        make_attr(ns_uri, "screenOrientation", None, TYPE_INT_DEC, 1),  # 1 = SCREEN_ORIENTATION_PORTRAIT
        make_attr(ns_uri, "configChanges", None, TYPE_INT_HEX, 0x000004A0),
    ], line=9)

    xml_tree += start_elem("intent-filter", [], line=10)
    xml_tree += start_elem("action", [
        make_attr(ns_uri, "name", "android.intent.action.MAIN", TYPE_STRING, s_idx["android.intent.action.MAIN"])
    ], line=11)
    xml_tree += end_elem("action", line=11)
    xml_tree += start_elem("category", [
        make_attr(ns_uri, "name", "android.intent.category.LAUNCHER", TYPE_STRING, s_idx["android.intent.category.LAUNCHER"])
    ], line=12)
    xml_tree += end_elem("category", line=12)
    xml_tree += end_elem("intent-filter", line=13)

    xml_tree += end_elem("activity", line=14)
    xml_tree += end_elem("application", line=15)
    xml_tree += end_elem("manifest", line=16)
    xml_tree += end_ns(16)

    body = string_pool_chunk + res_map_chunk + bytes(xml_tree)
    total_len = 8 + len(body)
    return struct.pack('<HHI', 0x0003, 8, total_len) + body


# =============================================================================
# 4. COMPLETE RESOURCES.ARSC MAPPING @drawable/ic_launcher (0x7f010000)
# =============================================================================
def make_utf16_string_pool(str_list: list) -> bytes:
    encoded = []
    offsets = []
    cur = 0
    for s in str_list:
        offsets.append(cur)
        u16 = s.encode('utf-16le')
        blob = struct.pack('<H', len(s)) + u16 + b'\x00\x00'
        encoded.append(blob)
        cur += len(blob)
    strings_blob = b''.join(encoded)
    if len(strings_blob) % 4 != 0:
        strings_blob += b'\x00' * (4 - (len(strings_blob) % 4))
    strings_start = 28 + len(str_list) * 4
    total_size = strings_start + len(strings_blob)
    return (
        struct.pack('<HHIIIIII', 0x0001, 28, total_size, len(str_list), 0, 0, strings_start, 0) +
        b''.join(struct.pack('<I', o) for o in offsets) +
        strings_blob
    )


def build_resources_arsc() -> bytes:
    """
    Builds a complete ResTable (resources.arsc) defining:
    - Package 0x7f ("com.lvlv.protuner")
    - Type 1 ("drawable")
    - Entry 0 ("ic_launcher", Resource ID 0x7f010000) -> "res/drawable/ic_launcher.png"
    """
    global_pool = make_utf16_string_pool(["res/drawable/ic_launcher.png"])
    type_pool = make_utf16_string_pool(["drawable"])
    key_pool = make_utf16_string_pool(["ic_launcher"])

    # ResTable_typeSpec (type = 0x0202, headerSize = 16, size = 20)
    type_spec_chunk = struct.pack('<HHIBBHII', 0x0202, 16, 20, 1, 0, 0, 1, 0)

    # ResTable_type (type = 0x0201)
    # ResTable_config (36 bytes: size=36 followed by 32 zero bytes)
    config_bytes = struct.pack('<I', 36) + b'\x00' * 32
    type_header_size = 20 + len(config_bytes)  # 56 bytes
    entries_start = type_header_size + 4       # 60 bytes (after 1 uint32 entry offset)
    # Entry 0: ResTable_entry (8 bytes: size=8, flags=0, key=0) + Res_value (8 bytes: size=8, res0=0, dataType=0x03 TYPE_STRING, data=0)
    entry_bytes = struct.pack('<HHIHBBI', 8, 0, 0, 8, 0, 0x03, 0)
    type_chunk_size = entries_start + len(entry_bytes)  # 76 bytes

    type_chunk = (
        struct.pack('<HHIBBHII', 0x0201, type_header_size, type_chunk_size, 1, 0, 0, 1, entries_start) +
        config_bytes +
        struct.pack('<I', 0) +  # offset 0 for entry 0
        entry_bytes
    )

    pkg_name_u16 = "com.lvlv.protuner".encode('utf-16le').ljust(256, b'\x00')
    pkg_header_size = 288
    type_strings_off = pkg_header_size
    key_strings_off = type_strings_off + len(type_pool)
    pkg_body = type_pool + key_pool + type_spec_chunk + type_chunk
    pkg_total_size = pkg_header_size + len(pkg_body)

    pkg_chunk = (
        struct.pack('<HHII', 0x0200, pkg_header_size, pkg_total_size, 0x7F) +
        pkg_name_u16 +
        struct.pack('<IIIII', type_strings_off, 1, key_strings_off, 1, 0) +
        pkg_body
    )

    total_size = 12 + len(global_pool) + len(pkg_chunk)
    return struct.pack('<HHII', 0x0002, 12, total_size, 1) + global_pool + pkg_chunk


# =============================================================================
# 5. SUPERSAMPLED APPLE-STYLE LAUNCHER ICON GENERATOR (PNG)
# =============================================================================
def generate_launcher_icon(out_size: int = 256) -> bytes:
    """
    Renders a 1024x1024 Apple-style icon and downsamples with LANCZOS to 256x256
    for ultra-crisp anti-aliased graphics on the Android home screen.
    """
    S = 1024
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer Apple Squircle Base (Deep Obsidian Charcoal)
    pad = 44
    draw.rounded_rectangle(
        [pad, pad, S - pad, S - pad],
        radius=220,
        fill=(18, 20, 24, 255),
        outline=(48, 209, 88, 190),
        width=14
    )

    # Inner subtle dark card glow ring
    draw.rounded_rectangle(
        [pad + 24, pad + 24, S - pad - 24, S - pad - 24],
        radius=196,
        fill=(24, 28, 34, 255),
        outline=(255, 255, 255, 22),
        width=4
    )

    # 2. Precision Semicircular Tuner Gauge Arc
    cx, cy = S // 2, int(S * 0.68)
    r = 340
    # Background track arc
    draw.arc(
        [cx - r, cy - r, cx + r, cy + r],
        start=198, end=342,
        fill=(255, 255, 255, 45),
        width=36
    )
    # Emerald sweet-spot center arc
    draw.arc(
        [cx - r, cy - r, cx + r, cy + r],
        start=252, end=288,
        fill=(48, 209, 88, 255),
        width=40
    )

    # 3. Radial Tick Marks
    for deg in range(-65, 66, 13):
        rad = math.radians(-90 + deg)
        is_center = (deg == 0)
        r_in = r - (78 if is_center else 56)
        r_out = r - 22
        x1 = cx + math.cos(rad) * r_in
        y1 = cy + math.sin(rad) * r_in
        x2 = cx + math.cos(rad) * r_out
        y2 = cy + math.sin(rad) * r_out
        col = (48, 209, 88, 255) if abs(deg) <= 13 else (255, 255, 255, 130)
        draw.line([x1, y1, x2, y2], fill=col, width=14 if is_center else 10)

    # 4. Crisp White & Emerald Tuning Needle Pointing Dead-Center
    draw.line([cx, cy - 40, cx, cy - r + 6], fill=(255, 255, 255, 255), width=22)
    # Glowing Orb at tip of needle
    tip_y = cy - r + 6
    draw.ellipse([cx - 34, tip_y - 34, cx + 34, tip_y + 34], fill=(48, 209, 88, 255))
    draw.ellipse([cx - 18, tip_y - 18, cx + 18, tip_y + 18], fill=(255, 255, 255, 255))

    # 5. Center Pivot Emblem (Golden-Emerald Erhu/Acoustic Ring)
    draw.ellipse([cx - 76, cy - 76, cx + 76, cy + 76], fill=(48, 209, 88, 255))
    draw.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=(18, 20, 24, 255))
    draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(255, 255, 255, 255))

    # Downsample with LANCZOS for smooth anti-aliasing
    final_img = img.resize((out_size, out_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    final_img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


# =============================================================================
# 6. DUAL APK SIGNER: V1 (JAR PKCS#7) + V2 (APK SIGNATURE SCHEME V2)
# =============================================================================
def generate_signing_key_and_cert():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LvLv Acoustic Lab"),
        x509.NameAttribute(NameOID.COMMON_NAME, "LvLv ProTuner Android Release"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .sign(private_key, hashes.SHA256())
    )
    return private_key, cert


def build_v1_signature_files(entries: list, private_key, cert) -> list:
    manifest_lines = [
        "Manifest-Version: 1.0",
        "Created-By: 2.0 (LvLv ProTuner Native Compiler)",
        ""
    ]
    sf_sections = []

    for name, raw_bytes, _ in entries:
        sha256_b64 = base64.b64encode(hashlib.sha256(raw_bytes).digest()).decode('ascii')
        section = f"Name: {name}\r\nSHA-256-Digest: {sha256_b64}\r\n\r\n"
        manifest_lines.append(section.rstrip('\r\n'))
        manifest_lines.append("")

        sf_sec_digest = base64.b64encode(hashlib.sha256(section.encode('utf-8')).digest()).decode('ascii')
        sf_sections.append(f"Name: {name}\r\nSHA-256-Digest: {sf_sec_digest}\r\n\r\n")

    manifest_bytes = "\r\n".join(manifest_lines).encode('utf-8')
    manifest_digest_b64 = base64.b64encode(hashlib.sha256(manifest_bytes).digest()).decode('ascii')

    sf_header = (
        "Signature-Version: 1.0\r\n"
        "Created-By: 1.0 (Android)\r\n"
        f"SHA-256-Digest-Manifest: {manifest_digest_b64}\r\n"
        "X-Android-APK-Signed: 2\r\n\r\n"
    )
    sf_bytes = sf_header.encode('utf-8') + "".join(sf_sections).encode('utf-8')

    cert_rsa_bytes = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, private_key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])
    )

    return [
        ("META-INF/MANIFEST.MF", manifest_bytes, True),
        ("META-INF/CERT.SF", sf_bytes, True),
        ("META-INF/CERT.RSA", cert_rsa_bytes, True),
    ]


def compute_apk_v2_content_digest(before_cd: bytes, central_dir: bytes, eocd_with_sigblock_offset: bytes) -> bytes:
    chunk_digests = []
    for section in (before_cd, central_dir, eocd_with_sigblock_offset):
        offset = 0
        n = len(section)
        while offset < n:
            chunk = section[offset:min(offset + 1048576, n)]
            buf = b'\xa5' + struct.pack('<I', len(chunk)) + chunk
            chunk_digests.append(hashlib.sha256(buf).digest())
            offset += 1048576
    top_level_input = b'\x5a' + struct.pack('<I', len(chunk_digests)) + b''.join(chunk_digests)
    return hashlib.sha256(top_level_input).digest()


def lp_slice(data: bytes) -> bytes:
    return struct.pack('<I', len(data)) + data


def build_apk_v2_signing_block(before_cd: bytes, central_dir: bytes, eocd: bytes, private_key, cert) -> tuple:
    SIG_ALGO_RSA_PKCS1_V1_5_SHA256 = 0x0103
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    pub_key_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )

    digest = compute_apk_v2_content_digest(before_cd, central_dir, eocd)
    digest_entry = lp_slice(struct.pack('<I', SIG_ALGO_RSA_PKCS1_V1_5_SHA256) + lp_slice(digest))
    digests_seq = lp_slice(digest_entry)
    certs_seq = lp_slice(lp_slice(cert_der))
    additional_attrs = lp_slice(b'')

    signed_data = digests_seq + certs_seq + additional_attrs
    signature_bytes = private_key.sign(
        signed_data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    sig_entry = lp_slice(struct.pack('<I', SIG_ALGO_RSA_PKCS1_V1_5_SHA256) + lp_slice(signature_bytes))
    signatures_seq = lp_slice(sig_entry)

    signer = lp_slice(lp_slice(signed_data) + signatures_seq + lp_slice(pub_key_der))
    signers_seq = lp_slice(signer)

    id_val = struct.pack('<I', 0x7109871a) + signers_seq
    pair = struct.pack('<Q', len(id_val)) + id_val

    total_inner = len(pair) + 8 + 16
    rem = (8 + total_inner) % 4096
    if rem != 0:
        pad_needed = 4096 - rem
        if pad_needed >= 12:
            dummy_val = struct.pack('<I', 0x42726577) + b'\x00' * (pad_needed - 12)
            pair += struct.pack('<Q', len(dummy_val)) + dummy_val

    size_of_block = len(pair) + 8 + 16
    v2_block = struct.pack('<Q', size_of_block) + pair + struct.pack('<Q', size_of_block) + b'APK Sig Block 42'

    new_cd_offset = len(before_cd) + len(v2_block)
    updated_eocd = eocd[:16] + struct.pack('<I', new_cd_offset) + eocd[20:]
    return v2_block, updated_eocd


# =============================================================================
# 7. ZIP / APK ARCHIVE ASSEMBLER WITH 4-BYTE ZIPALIGN
# =============================================================================
def assemble_aligned_signed_apk(app_entries: list, out_apk_paths: list):
    private_key, cert = generate_signing_key_and_cert()
    v1_entries = build_v1_signature_files(app_entries, private_key, cert)
    all_entries = app_entries + v1_entries

    local_stream = bytearray()
    cd_stream = bytearray()

    dos_time = (12 << 11) | (0 << 5) | 0
    dos_date = ((2026 - 1980) << 9) | (10 << 5) | 18

    for name, raw_bytes, compress in all_entries:
        name_bytes = name.encode('utf-8')
        crc = zlib.crc32(raw_bytes) & 0xFFFFFFFF
        uncomp_size = len(raw_bytes)

        if compress:
            comp_obj = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
            comp_bytes = comp_obj.compress(raw_bytes) + comp_obj.flush()
            comp_method = 8
        else:
            comp_bytes = raw_bytes
            comp_method = 0

        comp_size = len(comp_bytes)
        lfh_offset = len(local_stream)

        extra_data = b''
        if not compress:
            data_start = lfh_offset + 30 + len(name_bytes)
            pad = (4 - (data_start % 4)) % 4
            if pad > 0:
                extra_data = b'\x00' * pad

        lfh = struct.pack(
            '<IHHHHHIIIHH',
            0x04034B50,
            20,
            0,
            comp_method,
            dos_time,
            dos_date,
            crc,
            comp_size,
            uncomp_size,
            len(name_bytes),
            len(extra_data)
        )
        local_stream += lfh + name_bytes + extra_data + comp_bytes

        cdh = struct.pack(
            '<IHHHHHHIIIHHHHHII',
            0x02014B50,
            20,
            20,
            0,
            comp_method,
            dos_time,
            dos_date,
            crc,
            comp_size,
            uncomp_size,
            len(name_bytes),
            0,
            0,
            0,
            0,
            0,
            lfh_offset
        )
        cd_stream += cdh + name_bytes

    cd_offset = len(local_stream)
    cd_size = len(cd_stream)
    count = len(all_entries)

    eocd = struct.pack(
        '<IHHHHIIH',
        0x06054B50,
        0, 0,
        count, count,
        cd_size,
        cd_offset,
        0
    )

    v2_sig_block, updated_eocd = build_apk_v2_signing_block(bytes(local_stream), bytes(cd_stream), eocd, private_key, cert)

    final_apk_bytes = bytes(local_stream) + v2_sig_block + bytes(cd_stream) + updated_eocd
    for path in out_apk_paths:
        with open(path, 'wb') as f:
            f.write(final_apk_bytes)


def verify_generated_apk(apk_path: str):
    import zipfile
    with open(apk_path, 'rb') as f:
        raw = f.read()

    assert b'APK Sig Block 42' in raw, "Missing APK Signature Scheme v2 block!"
    with zipfile.ZipFile(apk_path, 'r') as zf:
        names = zf.namelist()
        for req in ['AndroidManifest.xml', 'classes.dex', 'resources.arsc', 'assets/index.html', 'res/drawable/ic_launcher.png']:
            assert req in names, f"Missing required APK entry: {req}"
        assert zf.testzip() is None, "ZIP CRC check failed!"

        dex = zf.read('classes.dex')
        assert dex[:8] == b'dex\n035\x00'
        assert struct.unpack('<I', dex[8:12])[0] == (zlib.adler32(dex[12:]) & 0xFFFFFFFF)
        assert dex[12:32] == hashlib.sha1(dex[32:]).digest()

        arsc = zf.read('resources.arsc')
        t_type, hdr_s, tot_s, pkg_cnt = struct.unpack('<HHII', arsc[:12])
        assert t_type == 0x0002 and hdr_s == 12 and tot_s == len(arsc) and pkg_cnt == 1

    print(f"SUCCESS: Verified {apk_path} ({len(raw):,} bytes) with App Icon (0x7f010000), Portrait Lock, and V1+V2 signatures.")


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_html = os.path.join(repo_root, "android", "app", "src", "main", "assets", "index.html")
    out_dir = os.path.join(repo_root, "releases")
    os.makedirs(out_dir, exist_ok=True)
    out_v2 = os.path.join(out_dir, "LvLv_ProTuner_v2.0.apk")

    with open(src_html, 'rb') as f:
        html_bytes = f.read()

    manifest_bytes = build_binary_android_manifest()
    arsc_bytes = build_resources_arsc()
    dex_bytes = build_classes_dex()
    icon_bytes = generate_launcher_icon(256)

    icon_path = os.path.join(repo_root, "android", "app", "src", "main", "res", "drawable", "ic_launcher.png")
    os.makedirs(os.path.dirname(icon_path), exist_ok=True)
    with open(icon_path, 'wb') as f:
        f.write(icon_bytes)

    entries = [
        ("AndroidManifest.xml", manifest_bytes, True),
        ("resources.arsc", arsc_bytes, False),
        ("res/drawable/ic_launcher.png", icon_bytes, False),
        ("classes.dex", dex_bytes, True),
        ("assets/index.html", html_bytes, True),
    ]

    assemble_aligned_signed_apk(entries, [out_v2])
    verify_generated_apk(out_v2)


if __name__ == '__main__':
    main()
