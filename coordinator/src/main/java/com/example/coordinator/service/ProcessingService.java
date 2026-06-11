package com.example.coordinator.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import org.springframework.core.ParameterizedTypeReference;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import com.example.coordinator.model.UserRequest;

import com.example.shared.model.LLMRequest;
import com.example.shared.model.RecipeQuery;
import com.example.shared.model.RecipeQueryResult;
import com.example.shared.model.UserIntent;

import java.util.concurrent.LinkedBlockingQueue;

import java.util.ArrayList;
import java.util.Random;
import java.util.List;
import java.util.HashSet;
import java.util.Arrays;

@Service
public class ProcessingService {

    private final RestTemplate restTemplate;
    private final RequestStorage storage;
    private boolean isLeader;

    private final HashSet<String> llmNodes = new HashSet<>();
    private final HashSet<String> dbNodes = new HashSet<>();

    private final LinkedBlockingQueue<String> requestQueue;

    public ProcessingService(
            RestTemplate restTemplate,
            RequestStorage storage,
            @Value("${coordinator.llm-nodes:}") String configuredLlmNodes) {
        this.restTemplate = restTemplate;
        this.storage = storage;
        isLeader = false;

        this.requestQueue = new LinkedBlockingQueue<>(100);
        Arrays.stream(configuredLlmNodes.split(","))
                .map(String::trim)
                .filter(node -> !node.isEmpty())
                .forEach(llmNodes::add);
    }

    public void setIsLeader(boolean input) {
        this.isLeader = input;
    }

    public boolean getIsLeader() {
        return this.isLeader;
    }

    public boolean apply(String id, String type) {
        // if nodes is llm, add to llmNodes
        // if nodes is db, add to dbNodes
        // if this node is leader, apply to other nodes too.
        return true;
    }

    public void updateQueue() { 
        requestQueue.addAll(storage.getRequestList());
    } 

    public boolean addToQueue(String id) {
         try {
            requestQueue.put(id);
            return true;
        } catch (Exception e) {return false;}
    }

    public void processingThread() {
        // add time out??
        Thread checkingThread = new Thread(() -> {
            while (isLeader) { 
                try {
                    String id = requestQueue.take();
                    UserRequest request = storage.getRequest(id);

                    if (request.getState().equals("received")) {
                        LLMRequest llmRequest = new LLMRequest();
                        llmRequest.setUserQuery(request.getUserQuery());
                        RecipeQuery result = sendToLLMNode(llmRequest);

                        if (result != null) {
                            request.setState("formatted");
                            request.setRecipeQuery(result);
                            storage.storeRequest(id, request);
                            this.addToQueue(id);
                            storage.broadCastCopy(request);
                        } else {
                            System.out.println("No result, request failed.");
                            storage.deleteRequest(id);
                        }

                    } else if (request.getState().equals("formatted")) {
                        RecipeQuery recipeQuery = request.getRecipeQuery();
                        List<RecipeQueryResult> result = sendToDBNode(recipeQuery);

                        if (result != null) {
                            request.setState("unformatted results");
                            request.setRecipeQueryResults(result);
                            storage.storeRequest(id, request);
                            this.addToQueue(id);
                            storage.broadCastCopy(request);
                        } else {
                            System.out.println("No result, request failed.");
                            storage.deleteRequest(id);
                        }

                        Thread.sleep(5000); 
                        request.setState("unformatted result");
                        storage.storeRequest(id, request);
                        this.addToQueue(id);
                        storage.broadCastCopy(request);

                    } else if (request.getState().equals("unformatted result")) {

                        // get the llm node to process
                        // added all the new result back to request

                        Thread.sleep(5000); 
                        request.setState("done");
                        request.setResult("final result is here");
                        storage.storeRequest(id, request);
                        storage.broadCastCopy(request);
                        
                    } else {
                        System.out.println("Something went very wrong");
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    System.err.println("The sleep was interrupted.");
                } catch (Exception e) {
                    System.out.println("The node cannot be called");
                    e.printStackTrace();
                }
            }
        });

        checkingThread.setDaemon(true); 
        checkingThread.start();
    }

    private RecipeQuery sendToLLMNode(LLMRequest llmRequest) {
        int numberOfNodes = llmNodes.size();
        if (numberOfNodes > 0)  {
            int attempt = 0;
            do {
                attempt = attempt + 1;
                String node = (String) llmNodes.toArray()[new Random().nextInt(numberOfNodes)];
                try {
                    String targetUrl = "http://localhost:" + node + "/llm/decompose";
                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    HttpEntity<LLMRequest> entity = new HttpEntity<>(llmRequest, headers);

                    UserIntent intent = restTemplate.postForObject(targetUrl, entity, UserIntent.class);
                    if (intent == null) {
                        return null;
                    }

                    RecipeQuery recipeQuery = new RecipeQuery();
                    recipeQuery.setRecipeQuery(intent.getRecipeQuery());
                    recipeQuery.setRecipeFilters(intent.getRecipeFilters());
                    return recipeQuery;
                } catch (Exception e) {System.out.println("Calling llm service failed.");}
            } while (attempt < 5);
            return null;
        } else {
            System.out.println("No llm nodes found");
            return null;
        }
    }
    
    private List<RecipeQueryResult> sendToDBNode(RecipeQuery recipeQuery) {
        int numberOfNodes = dbNodes.size();
        List<RecipeQueryResult> results = new ArrayList<>();
        if (numberOfNodes >= 0)  {
            for (String node : dbNodes) {
                try {
                    String targetUrl = "http://localhost:" + node + "/recipes/search";
                    HttpHeaders headers = new HttpHeaders();
                    headers.setContentType(MediaType.APPLICATION_JSON);
                    HttpEntity<RecipeQuery> entity = new HttpEntity<>(recipeQuery, headers);

                    ResponseEntity<List<RecipeQueryResult>> response = restTemplate.exchange(
                            targetUrl, HttpMethod.POST, entity,
                            new ParameterizedTypeReference<List<RecipeQueryResult>>() {}
                    );

                    if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                        results.addAll(response.getBody());
                    }
                } catch (Exception e) {System.out.println("Calling RECIPE NODE service failed.");}
            }
            return results;
        } else {
            System.out.println("No recipe nodes found");
            return null;
        }
    }
}
