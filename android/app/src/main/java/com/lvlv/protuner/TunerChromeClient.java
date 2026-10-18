package com.lvlv.protuner;

import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;

public class TunerChromeClient extends WebChromeClient {
    @Override
    public void onPermissionRequest(PermissionRequest request) {
        // Automatically grant WebAudio microphone capture inside the Android WebView
        request.grant(request.getResources());
    }
}
