package com.example.shared.model;

public class NutritionFilters{
    private String foodName;             
    private Double maxCalories;          
    private Double minProtein;          
    private Double maxFat;     
    private Double maxCarbs;           
    private Double minFiber;          
    private Double maxSugar;        
    private Double maxSodium;          
    private Boolean isHighProtein;     
    private Boolean isLowCarb;      
    private Boolean isLowCalorie;        

    public NutritionFilters(){}

    public String getFoodName() {
        return foodName;
    }
    public void setFoodName(String foodName) {
        this.foodName = foodName;
    }

    public Double getMaxCalories() {
        return maxCalories;
    }
    public void setMaxCalories(Double maxCalories) {
        this.maxCalories = maxCalories;
    }

    public Double getMinProtein() {
        return minProtein;
    }
    public void setMinProtein(Double minProtein) {
        this.minProtein = minProtein;
    }

    public Double getMaxFat() {
        return maxFat;
    }
    public void setMaxFat(Double maxFat) {
        this.maxFat = maxFat;
    }

    
    public Double getMaxCarbs() {
        return maxCarbs;
    }
    public void setMaxCarbs(Double maxCarbs) {
        this.maxCarbs = maxCarbs;
    }

    public Double getMinFiber() {
        return minFiber;
    }
    public void setMinFiber(Double minFiber) {
        this.minFiber = minFiber;
    }

    public Double getMaxSugar() {
        return maxSugar;
    }
    public void setMaxSugar(Double maxSugar) {
        this.maxSugar = maxSugar;
    }

    public Double getMaxSodium() {
        return maxSodium;
    }
    public void setMaxSodium(Double maxSodium) {
        this.maxSodium = maxSodium;
    }

    public Boolean getIsHighProtein() {
        return isHighProtein;
    }
    public void setIsHighProtein(Boolean isHighProtein) {
        this.isHighProtein = isHighProtein;
    }

    public Boolean getIsLowCarb() {
        return isLowCarb;
    }
    public void setIsLowCarb(Boolean isLowCarb) {
        this.isLowCarb = isLowCarb;
    }

    public Boolean getIsLowCalorie() {
        return isLowCalorie;
    }
    public void setIsLowCalorie(Boolean isLowCalorie) {
        this.isLowCalorie = isLowCalorie;
    }
}