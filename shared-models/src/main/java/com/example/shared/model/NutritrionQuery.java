package com.example.shared.model;

public class NutritionQuery{
    private String nutritionQuery;
    private NutritionFilters filters;
    private StatusState state;

    public NutritionQuery(){}

    public String getNutritrionQuery(){
        return nutritionQuery;
    }
    public void setNutritionQuery(String query){
        this.nutritionQuery = query;
    }

    public NutritionFilters getNutritionFilters(){
        return filters;
    }
    public void setNutritionFilters(NutritionFilters filters){
        this.filters = filters;
    }

    public StatusState getState(){
        return state;
    }
    public void getState(StatusState state){
        this.state = state;
    }
}