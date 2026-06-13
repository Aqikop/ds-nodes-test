package com.example.shared.model;

import java.util.List;

public class UserIntent {
    private List<String> collections;        // ["recipes"] | ["nutrition"] | ["recipes","nutrition"] (choose which datasets to query)
    private boolean estimateNutrition;
    private String recipeQuery;              // recipe_query (parse user's input into searchable semantic)
    private String nutritionQuery;           // nutrition_query
    private RecipeFiltersDTO recipeFilters;
    private NutritionFiltersDTO nutritionFilters;

    public UserIntent() {}

    public List<String> getCollections() {
        return collections;
    }
    public void setCollections(List<String> collections) {
        this.collections = collections;
    }

    public boolean isEstimateNutrition() {
        return estimateNutrition;
    }
    public void setEstimateNutrition(boolean estimateNutrition) {
        this.estimateNutrition = estimateNutrition;
    }

    public String getRecipeQuery() {
        return recipeQuery;
    }
    public void setRecipeQuery(String recipeQuery) {
        this.recipeQuery = recipeQuery;
    }

    public String getNutritionQuery() {
        return nutritionQuery;
    }
    public void setNutritionQuery(String nutritionQuery) {
        this.nutritionQuery = nutritionQuery;
    }

    public RecipeFiltersDTO getRecipeFilters() {
        return recipeFilters;
    }
    public void setRecipeFilters(RecipeFiltersDTO recipeFilters) {
        this.recipeFilters = recipeFilters;
    }

    public NutritionFiltersDTO getNutritionFilters() {
        return nutritionFilters;
    }
    public void setNutritionFilters(NutritionFiltersDTO nutritionFilters) {
        this.nutritionFilters = nutritionFilters;
    }
}