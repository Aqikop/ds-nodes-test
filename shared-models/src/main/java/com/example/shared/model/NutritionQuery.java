package com.example.shared.model;

public class NutritionQuery {
    private String nutritionQuery;
    private NutritionFilters nutritionFilters;
    private StatusState state;

    public NutritionQuery(){}

    public String getNutritionQuery(){
        return nutritionQuery;
    }
    public void setNutritionQuery(String query){
        this.nutritionQuery = query;
    }

    public NutritionFilters getNutritionFilters(){
        return nutritionFilters;
    }
    public void setNutritionFilters(NutritionFilters nutritionFilters){
        this.nutritionFilters = nutritionFilters;
    }

    public StatusState getState(){
        return state;
    }
    public void setState(StatusState state){
        this.state = state;
    }
}
