package com.tradingindicator.alerts;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    final ExecutorService network=Executors.newSingleThreadExecutor();
    State state;Client client;FeedStore store;LinearLayout root;TextView status;ListView list;ArrayList<JSONObject> messages=new ArrayList<>();
    final ArrayList<Long> back=new ArrayList<>();long before=Long.MAX_VALUE;boolean loading=false,receiverRegistered=false;
    final BroadcastReceiver receiver=new BroadcastReceiver(){public void onReceive(Context c,Intent i){if(before==Long.MAX_VALUE)showCached();}};
    int dp(int value){return (int)(value*getResources().getDisplayMetrics().density);}
    TextView text(String value,int size){TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(Color.rgb(231,238,245));view.setPadding(0,dp(6),0,dp(6));return view;}
    Button button(String value,LinearLayout parent,View.OnClickListener action){Button view=new Button(this);view.setText(value);view.setOnClickListener(action);parent.addView(view);return view;}
    void note(String value){runOnUiThread(()->{if(status!=null)status.setText(value);});}
    void frame(){root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(16),dp(14),dp(16),dp(10));root.setFitsSystemWindows(true);root.setBackgroundColor(Color.rgb(20,25,31));setContentView(root);root.addView(text("Trading Alerts",25));status=text("",13);root.addView(status);}
    @Override public void onCreate(Bundle saved){super.onCreate(saved);state=new State(this);client=new Client(this);store=new FeedStore(this);Messages.channels(this);if(state.get("owner").isEmpty())login();else {inbox();network.execute(this::setupPush);}openIntent(getIntent());}
    @Override public void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);openIntent(intent);}
    void openIntent(Intent intent){if(intent!=null&&intent.hasExtra("seq")&&!state.get("owner").isEmpty()){before=intent.getLongExtra("seq",0)+1;back.clear();showCached();sync();}}
    @Override public void onResume(){super.onResume();IntentFilter filter=new IntentFilter(Messages.UPDATE);if(Build.VERSION.SDK_INT>=33)registerReceiver(receiver,filter,Context.RECEIVER_NOT_EXPORTED);else registerReceiver(receiver,filter);receiverRegistered=true;}
    @Override public void onPause(){super.onPause();if(receiverRegistered){unregisterReceiver(receiver);receiverRegistered=false;}}
    @Override public void onDestroy(){super.onDestroy();network.shutdown();store.close();}
    EditText field(String hint,boolean password){EditText input=new EditText(this);input.setHint(hint);input.setTextColor(Color.WHITE);input.setHintTextColor(Color.LTGRAY);input.setSingleLine(true);if(password)input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);root.addView(input);return input;}
    void login(){frame();root.addView(text("Connect to your laptop",18));EditText address=field("Laptop HTTPS address",false);address.setText(state.get("origin"));EditText owner=field("Username",false);EditText password=field("Password",true);
        Button connect=button("Connect",root,v->{
            final String origin,username=owner.getText().toString().trim(),secret=password.getText().toString();try{origin=Client.origin(address.getText().toString());}catch(Exception e){note(e.getMessage());return;}
            v.setEnabled(false);note("Signing in…");network.execute(()->{try{
                state.put("origin",origin);JSONObject identity=client.api("/api/login",new JSONObject().put("username",username).put("password",secret).put("remember",true));state.put("owner",identity.getString("username"));
                runOnUiThread(()->{password.setText("");before=Long.MAX_VALUE;back.clear();inbox();if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},10);});
                setupPush();
            }catch(Exception e){note(e.getMessage());runOnUiThread(()->v.setEnabled(true));}});
        });root.addView(text("Use the private address supplied by your laptop operator. No charts or orders are shown in this app.",13));}
    void inbox(){frame();root.addView(text(state.get("owner")+" · saved notifications",16));
        Switch notifications=new Switch(this);notifications.setText("Notifications");notifications.setTextColor(Color.WHITE);notifications.setChecked(state.enabled());root.addView(notifications);
        Switch sounds=new Switch(this);sounds.setText("Sound");sounds.setTextColor(Color.WHITE);sounds.setChecked(state.sound());root.addView(sounds);
        notifications.setOnCheckedChangeListener((view,on)->{state.enabled(on);if(on&&Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},10);updateDevice();});
        sounds.setOnCheckedChangeListener((view,on)->{state.sound(on);updateDevice();});
        LinearLayout actions=new LinearLayout(this);root.addView(actions);button("Refresh",actions,v->{before=Long.MAX_VALUE;back.clear();sync();});button("Sign out",actions,v->signOut());
        list=new ListView(this);list.setDivider(null);root.addView(list,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout pages=new LinearLayout(this);root.addView(pages);button("Newer",pages,v->{if(!back.isEmpty()){before=back.remove(back.size()-1);showCached();}});button("Older history",pages,v->{if(!messages.isEmpty()){back.add(before);before=messages.get(messages.size()-1).optLong("seq");showCached();sync();}});
        showCached();sync();
    }
    void showCached(){if(list==null)return;messages=store.list(state,before,50);list.setAdapter(new BaseAdapter(){public int getCount(){return messages.size();}public Object getItem(int i){return messages.get(i);}public long getItemId(int i){return messages.get(i).optLong("seq");}
        public View getView(int i,View reuse,ViewGroup parent){JSONObject event=messages.get(i);LinearLayout card=new LinearLayout(MainActivity.this);card.setOrientation(LinearLayout.VERTICAL);card.setPadding(dp(12),dp(10),dp(12),dp(10));GradientDrawable background=new GradientDrawable();background.setColor(Color.rgb(32,40,50));background.setCornerRadius(dp(9));background.setStroke(dp(1),Color.rgb(70,85,101));card.setBackground(background);
            TextView stamp=text(CardText.time(event),12);card.addView(stamp);JSONObject details=event.optJSONObject("details");String side=details==null?event.optString("name"):details.optString("side",event.optString("name"));TextView title=text(event.optString("symbol")+" "+event.optString("interval")+" "+side,18);title.setTypeface(null,Typeface.BOLD);card.addView(title);card.addView(text(CardText.body(event),14));return card;}});}
    void sync(){if(loading||state.get("owner").isEmpty())return;loading=true;final String owner=state.get("owner"),origin=state.get("origin");final long page=before;note("Synchronizing history…");network.execute(()->{try{
            JSONObject packet=client.api("/api/alerts/history?limit=50"+(page==Long.MAX_VALUE?"":"&before="+page),null);JSONArray rows=packet.getJSONArray("history");if(!owner.equals(state.get("owner"))||!origin.equals(state.get("origin")))return;
            for(int i=0;i<rows.length();i++)store.save(state,rows.getJSONObject(i));runOnUiThread(()->{if(page==before){showCached();note(rows.length()==0?"No older messages. All received history stays saved.":"History synchronized. Older history loads silently.");}});
        }catch(Exception e){note("Showing saved messages. "+e.getMessage());}finally{loading=false;}});}
    void setupPush(){try{JSONObject config=client.api("/api/android/config",null);if(!config.optBoolean("ready")){note("History works. Laptop Firebase setup is needed for background alerts.");return;}
            if(!BuildConfig.APPLICATION_ID.equals(config.optString("package_name")))throw new Exception("The laptop expects a different Android app package.");
            if(!state.get("origin").equals(config.optString("origin")))throw new Exception("Connect using the laptop’s configured HTTPS address.");
            String old=state.get("firebase");if(!old.isEmpty()&&!new JSONObject(old).optString("project_id").equals(config.optString("project_id")))throw new Exception("Clear this app’s storage before changing Firebase projects.");
            state.put("firebase",config.toString());App.initialize(config);FirebaseMessaging.getInstance().getToken().addOnCompleteListener(task->{if(task.isSuccessful()){state.put("token",task.getResult());updateDevice();}else note("Firebase connection failed. Check the laptop setup.");});
        }catch(Exception e){note(e.getMessage());}}
    void updateDevice(){network.execute(()->{try{client.register();note("Device settings saved. Android system notification settings can also mute sounds.");}catch(Exception e){note("Saved on this phone; laptop update pending. "+e.getMessage());}});}
    void signOut(){note("Disconnecting…");network.execute(()->{try{if(!state.get("token").isEmpty())client.api("/api/android/unsubscribe",new JSONObject().put("token",state.get("token")));client.api("/api/logout",new JSONObject());}catch(Exception ignored){}finally{if(!FirebaseApp.getApps(this).isEmpty())FirebaseMessaging.getInstance().deleteToken();state.logout();getSystemService(NotificationManager.class).cancelAll();runOnUiThread(this::login);}});}
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants){super.onRequestPermissionsResult(code,permissions,grants);if(code==10){boolean allowed=grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED;state.enabled(allowed);updateDevice();if(!allowed)note("Android notification permission is off. History is still saved.");}}
}
