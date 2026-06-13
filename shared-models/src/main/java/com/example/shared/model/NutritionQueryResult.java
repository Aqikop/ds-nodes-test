package com.example.shared.model;

import java.util.Map;

public class NutritionQueryResult{
    private String itemName;
    private String payload;
    private Double score;
    private Map<String, Object> metadata;
    private StatusState state;

    public NutritionQueryResult() {}

    public String getItemName() {
        return itemName;
    }
    public void setItemName(String itemName) {
        this.itemName = itemName;
    }

    public String getPayload() {
        return payload;
    }
    public void setPayload(String payload) {
        this.payload = payload;
    }

    public Double getScore() {
        return score;
    }
    public void setScore(Double score) {
        this.score = score;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }
    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata;
    }

    public StatusState getState() {
        return state;
    }
    public void setState(StatusState state) {
        this.state = state;
    }
}