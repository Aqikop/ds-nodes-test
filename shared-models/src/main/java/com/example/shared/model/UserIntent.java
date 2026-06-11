package com.example.shared.model;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown=true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class UserIntent {
    private List<String> collections;        // ["recipes"] | ["nutrition"] | ["recipes","nutrition"] (choose which datasets to query)
    private boolean estimateNutrition;
    private String recipeQuery;              // recipe_query (parse user's input into searchable semantic)
    private String nutritionQuery;           // nutrition_query
    private RecipeFilters recipeFilters;
    private NutritionFilters nutritionFilters;

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

    public RecipeFilters getRecipeFilters() {
        return recipeFilters;
    }
    public void setRecipeFilters(RecipeFilters recipeFilters) {
        this.recipeFilters = recipeFilters;
    }

    public NutritionFilters getNutritionFilters() {
        return nutritionFilters;
    }
    public void setNutritionFilters(NutritionFilters nutritionFilters) {
        this.nutritionFilters = nutritionFilters;
    }
}