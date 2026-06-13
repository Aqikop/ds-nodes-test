package com.example.shared.model;

import java.util.List;

public class SearchResponse {
    private String answer;
    private List<RecipeQueryResult> recipes;
    private List<NutritionQueryResult> nutrition;
    private StatusState state;

    public SearchResponse() {}

    public String getAnswer() {
        return answer;
    }
    public void setAnswer(String answer) {
        this.answer = answer;
    }

    public List<RecipeQueryResult> getRecipes() {
        return recipes;
    }
    public void setRecipes(List<RecipeQueryResult> recipes) {
        this.recipes = recipes;
    }

    public List<NutritionQueryResult> getNutrition() {
        return nutrition;
    }
    public void setNutrition(List<NutritionQueryResult> nutrition) {
        this.nutrition = nutrition;
    }

    public StatusState getState() {
        return state;
    }
    public void setState(StatusState state) {
        this.state = state;
    }
}