package com.tradingindicator.alerts;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
import org.json.JSONObject;
import java.text.DateFormat;
import java.util.Date;

public final class Messages extends FirebaseMessagingService {
    static final String UPDATE="com.tradingindicator.alerts.UPDATE";
    static final String AUDIBLE="signals_audible_v1",SILENT="signals_silent_v1";
    public void onNewToken(String token){State state=new State(this);state.put("token",token);new Thread(()->{try{new Client(this).register();}catch(Exception ignored){}},"register-device").start();}
    static void channels(android.content.Context context){
        NotificationManager manager=context.getSystemService(NotificationManager.class);
        NotificationChannel audible=new NotificationChannel(AUDIBLE,"Signal alerts with sound",NotificationManager.IMPORTANCE_HIGH);
        audible.setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION),new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION).build());
        NotificationChannel silent=new NotificationChannel(SILENT,"Silent signal alerts",NotificationManager.IMPORTANCE_HIGH);silent.setSound(null,null);silent.enableVibration(false);
        manager.createNotificationChannel(audible);manager.createNotificationChannel(silent);
    }
    public void onMessageReceived(RemoteMessage message){
        State state=new State(this);
        if(!state.get("owner").equals(message.getData().get("owner"))||!state.get("origin").equals(message.getData().get("origin"))||state.get("owner").isEmpty())return;
        try{
            JSONObject event=new JSONObject(message.getData().get("event"));try(FeedStore store=new FeedStore(this)){store.save(state,event);}
            sendBroadcast(new Intent(UPDATE).setPackage(getPackageName()));
            if(!state.enabled()||android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)return;
            channels(this);Intent intent=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP).putExtra("seq",event.getLong("seq"));
            PendingIntent target=PendingIntent.getActivity(this,(int)(event.getLong("seq")&0x7fffffff),intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
            JSONObject details=event.optJSONObject("details");String side=details==null?event.optString("name"):details.optString("side",event.optString("name"));
            String title=event.optString("symbol")+" "+event.optString("interval")+" "+side;
            String body=CardText.body(event);
            Notification notification=new Notification.Builder(this,state.sound()?AUDIBLE:SILENT).setSmallIcon(R.drawable.ic_notification).setContentTitle(title).setContentText(body).setStyle(new Notification.BigTextStyle().bigText(body)).setWhen(event.optLong("created",System.currentTimeMillis())).setShowWhen(true).setContentIntent(target).setAutoCancel(true).build();
            getSystemService(NotificationManager.class).notify(state.get("origin")+"|"+state.get("owner")+"|"+event.getLong("seq"),0,notification);
        }catch(Exception ignored){}
    }
}
