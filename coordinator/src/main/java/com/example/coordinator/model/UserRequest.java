package com.example.coordinator.model;

import java.util.List;

import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;
import com.example.shared.model.StatusState;

import java.util.List;

public class UserRequest {
    private String id;
    private String state;
    private String userQuery;
    private RecipeQuery recipeQuery;
    private List<RecipeQueryResult> recipeQueryResults;
    private String result;

    public UserRequest() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getState() { return state; }
    public void setState(String state) { this.state = state; }

    public String getUserQuery() { return userQuery; }
    public void setUserQuery(String userQuery) { this.userQuery = userQuery; }

    public RecipeQuery getRecipeQuery() { return recipeQuery; }
    public void setRecipeQuery(RecipeQuery recipeQuery) { this.recipeQuery = recipeQuery; }

    public List<RecipeQueryResult> getRecipeQueryResults() { return recipeQueryResults; }
    public void setRecipeQueryResults(List<RecipeQueryResult> recipeQueryResults) { this.recipeQueryResults = recipeQueryResults; }

    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }
}