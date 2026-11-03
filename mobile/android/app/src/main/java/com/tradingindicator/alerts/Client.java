package com.tradingindicator.alerts;

import android.content.Context;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

final class Client {
    final State state;
    Client(Context context){state=new State(context);}
    static String origin(String input) throws Exception {
        URI uri=new URI(input.trim());String host=uri.getHost();
        boolean local=BuildConfig.DEBUG&&("localhost".equals(host)||"127.0.0.1".equals(host)||"10.0.2.2".equals(host));
        if(host==null||uri.getUserInfo()!=null||uri.getQuery()!=null||uri.getFragment()!=null||!("https".equals(uri.getScheme())||local&&"http".equals(uri.getScheme()))||!(uri.getPath()==null||uri.getPath().isEmpty()||uri.getPath().equals("/")))throw new Exception("Enter the laptop HTTPS address, without a path.");
        return new URI(uri.getScheme(),null,host.toLowerCase(java.util.Locale.ROOT),("https".equals(uri.getScheme())&&uri.getPort()==443?-1:uri.getPort()),null,null,null).toString();
    }
    JSONObject api(String path,JSONObject data) throws Exception {
        HttpURLConnection connection=(HttpURLConnection)new URL(state.get("origin")+path).openConnection();
        connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(10000);connection.setReadTimeout(15000);connection.setRequestProperty("Cookie",state.cookie());connection.setRequestProperty("Accept","application/json");
        try{
            if(data!=null){connection.setRequestMethod("POST");connection.setDoOutput(true);connection.setRequestProperty("Content-Type","application/json");try(var stream=connection.getOutputStream()){stream.write(data.toString().getBytes(StandardCharsets.UTF_8));}}
            int code=connection.getResponseCode();InputStream raw=code<400?connection.getInputStream():connection.getErrorStream();
            java.io.ByteArrayOutputStream output=new java.io.ByteArrayOutputStream();if(raw!=null){byte[] chunk=new byte[8192];int read;while((read=raw.read(chunk))!=-1){output.write(chunk,0,read);if(output.size()>2*1024*1024)throw new Exception("Server response too large");}raw.close();}String body=output.size()==0?"{}":output.toString("UTF-8");JSONObject packet=new JSONObject(body);
            if(code<200||code>=300)throw new Exception(packet.optString("error","Server request failed ("+code+")"));
            String cookie=connection.getHeaderField("Set-Cookie");if(cookie!=null&&cookie.startsWith("tradingbot_session="))state.cookie(cookie.split(";",2)[0]);
            return packet;
        }finally{connection.disconnect();}
    }
    void register() throws Exception {
        if(state.get("token").isEmpty()||state.get("owner").isEmpty())return;
        boolean permission=android.os.Build.VERSION.SDK_INT<33||App.context.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED;
        api("/api/android/subscribe",new JSONObject().put("token",state.get("token")).put("package_name",BuildConfig.APPLICATION_ID).put("enabled",state.enabled()&&permission).put("sound",state.sound()));
    }
}
