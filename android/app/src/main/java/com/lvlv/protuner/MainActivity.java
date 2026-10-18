package com.lvlv.protuner;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebSettings;
import android.webkit.WebView;

public class MainActivity extends Activity {
    private static final int REQ_RECORD_AUDIO = 1;
    private static final int FLAG_KEEP_SCREEN_ON = 128;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. Lock portrait orientation to prevent layout jumps while holding instruments
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);

        // 2. Keep screen awake while tuning & set seamless black system bars
        Window window = getWindow();
        window.addFlags(FLAG_KEEP_SCREEN_ON);
        window.setStatusBarColor(0xFF000000);
        window.setNavigationBarColor(0xFF000000);

        // 3. Request runtime microphone permission (Android 6.0+)
        requestPermissions(new String[]{"android.permission.RECORD_AUDIO"}, REQ_RECORD_AUDIO);

        // 4. Initialize zero-jitter hardware-accelerated WebView container
        WebView webView = new WebView(this);
        webView.setVerticalScrollBarEnabled(false);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setBackgroundColor(0xFF000000);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        // Lock 100% text zoom so system font size settings never cause layout shifts
        settings.setTextZoom(100);

        webView.setWebChromeClient(new TunerChromeClient());
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }
}
