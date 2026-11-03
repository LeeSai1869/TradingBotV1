package com.tradingindicator.alerts;

import android.app.Application;
import android.content.Context;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import org.json.JSONObject;

public final class App extends Application {
    static Context context;
    public void onCreate(){super.onCreate();context=this;try{String config=new State(this).get("firebase");if(!config.isEmpty())initialize(new JSONObject(config));}catch(Exception ignored){}}
    static void initialize(JSONObject cfg) throws Exception {
        if(!FirebaseApp.getApps(context).isEmpty())return;
        FirebaseApp.initializeApp(context,new FirebaseOptions.Builder().setApplicationId(cfg.getString("app_id")).setApiKey(cfg.getString("api_key")).setProjectId(cfg.getString("project_id")).setGcmSenderId(cfg.getString("sender_id")).build());
    }
}
