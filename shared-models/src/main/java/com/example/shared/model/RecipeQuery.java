package com.example.shared.model;

import java.util.List;

public class RecipeQuery {
    //@Description("List of ingredient or recipe name keywords for vector search")
    private String recipeQuery;
    private getRecipeFilters filters;
    private StatusState state;

    public RecipeQuery(){}

    public String getRecipeQuery(){
        return recipeQuery;
    }
    public void setRecipeQuery(String query){
        this.recipeQuery = query;
    }

    public RecipeFilters getRecipeFilters(){
        return filters;
    }
    public void setNutritionFilters(RecipeFilters filters){
        this.filters = filters;
    }

    public StatusState getState(){
        return state;
    }
    public void getState(StatusState state){
        this.state = state;
    }
}