package com.example.shared.model;

public class RecipeQuery {
    //@Description("List of ingredient or recipe name keywords for vector search")
    private String recipeQuery;
    private RecipeFilters recipeFilters;
    private StatusState state; 

    public RecipeQuery(){}

    public String getRecipeQuery(){
        return recipeQuery;
    }
    public void setRecipeQuery(String query){
        this.recipeQuery = query;
    }

    public RecipeFilters getRecipeFilters(){
        return recipeFilters;
    }
    
    public void setRecipeFilters(RecipeFilters recipeFilters){
        this.recipeFilters = recipeFilters;
    }

    public StatusState getState(){
        return state;
    }
    public void setState(StatusState state){
        this.state = state;
    }
}
