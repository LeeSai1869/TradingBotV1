package com.tradingindicator.alerts;

import org.json.JSONObject;
import java.text.DateFormat;
import java.util.Date;

final class CardText {
    static String number(JSONObject object,String key){Object value=object==null?null:object.opt(key);if(!(value instanceof Number)||!Double.isFinite(((Number)value).doubleValue()))return "Unavailable";return new java.text.DecimalFormat("0.##########").format(((Number)value).doubleValue());}
    static String body(JSONObject event){
        JSONObject d=event.optJSONObject("details");JSONObject upper=d==null?null:d.optJSONObject("upper"),lower=d==null?null:d.optJSONObject("lower");
        return "Price "+number(d,"price")+" · Confidence "+number(d,"confidence")+"/100\nSell zone upper "+number(upper,"high")+"\nBuy zone lower "+number(lower,"low");
    }
    static String time(JSONObject event){return DateFormat.getDateTimeInstance(DateFormat.MEDIUM,DateFormat.SHORT).format(new Date(event.optLong("created")));}
}
