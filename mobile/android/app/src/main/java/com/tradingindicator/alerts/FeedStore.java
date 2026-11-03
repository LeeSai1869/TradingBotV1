package com.tradingindicator.alerts;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.content.ContentValues;
import org.json.JSONObject;
import java.util.ArrayList;

final class FeedStore extends SQLiteOpenHelper {
    FeedStore(Context context){super(context,"inbox.db",null,1);}
    public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE messages(origin TEXT,owner TEXT,seq INTEGER,received INTEGER,payload TEXT NOT NULL,PRIMARY KEY(origin,owner,seq))");}
    public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion){throw new IllegalStateException("Inbox migration required");}
    void save(State state,JSONObject event) throws Exception {
        long seq=event.getLong("seq");ContentValues row=new ContentValues();row.put("origin",state.get("origin"));row.put("owner",state.get("owner"));row.put("seq",seq);row.put("received",System.currentTimeMillis());row.put("payload",event.toString());
        getWritableDatabase().insertWithOnConflict("messages",null,row,SQLiteDatabase.CONFLICT_IGNORE);
    }
    ArrayList<JSONObject> list(State state,long before,int limit){
        ArrayList<JSONObject> result=new ArrayList<>();try(var cursor=getReadableDatabase().rawQuery("SELECT payload FROM messages WHERE origin=? AND owner=? AND seq<? ORDER BY seq DESC LIMIT ?",new String[]{state.get("origin"),state.get("owner"),String.valueOf(before),String.valueOf(limit)})){
            while(cursor.moveToNext())try{result.add(new JSONObject(cursor.getString(0)));}catch(Exception ignored){}
        }return result;
    }
}
