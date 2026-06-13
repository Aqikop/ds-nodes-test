package com.example.shared.model;

import java.util.List;

public class RecipeFilters {
    private String mealType;
    private String cuisine;
    private List<String> cookingMethod;
    private String mainProtein;
    private List<String> dietFlags;
    private Integer maxIngredients;
    private Integer maxCookTime;
    private Boolean hasPicture;

    public RecipeFilters() {}

    public String getMealType() {
        return mealType;
    }
    public void setMealType(String mealType) {
        this.mealType = mealType;
    }

    public String getCuisine() {
        return cuisine;
    }
    public void setCuisine(String cuisine) {
        this.cuisine = cuisine;
    }

    public List<String> getCookingMethod() {
        return cookingMethod;
    }
    public void setCookingMethod(List<String> cookingMethod) {
        this.cookingMethod = cookingMethod;
    }

    public String getMainProtein() {
        return mainProtein;
    }
    public void setMainProtein(String mainProtein) {
        this.mainProtein = mainProtein;
    }

    public List<String> getDietFlags() {
        return dietFlags;
    }
    public void setDietFlags(List<String> dietFlags) {
        this.dietFlags = dietFlags;
    }

    public Integer getMaxIngredients() {
        return maxIngredients;
    }
    public void setMaxIngredients(Integer maxIngredients) {
        this.maxIngredients = maxIngredients;
    }

    public Integer getMaxCookTime() {
        return maxCookTime;
    }
    public void setMaxCookTime(Integer maxCookTime) {
        this.maxCookTime = maxCookTime;
    }

    public Boolean getHasPicture() {
        return hasPicture;
    }
    public void setHasPicture(Boolean hasPicture) {
        this.hasPicture = hasPicture;
    }
}