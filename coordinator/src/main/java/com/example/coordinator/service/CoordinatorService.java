package com.example.coordinator.service;

import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import com.example.coordinator.model.UserRequest;

import com.example.shared.model.LLMRequest;


@Service
public class CoordinatorService {

    private final RestTemplate restTemplate;
    private final ProcessingService processingService;
    private final RequestStorage storage;
    
    public CoordinatorService(RestTemplate restTemplate, 
            RequestStorage storage, ProcessingService processingService) {
        this.restTemplate = restTemplate;
        this.processingService = processingService;
        this.storage = storage;
    }

    public String search(LLMRequest request) { 
        if (processingService.getIsLeader()) {
            String id = UUID.randomUUID().toString(); 
            System.out.println("User Query: " + request.getUserQuery());

            UserRequest userRequest = new UserRequest();
            userRequest.setId(id);
            userRequest.setState("received");
            userRequest.setUserQuery(request.getUserQuery());

            storage.storeRequest(id, userRequest);
            processingService.addToQueue(id);
            storage.broadCastCopy(userRequest);

            return id;
        } else {
            return "Rejected, not leading.";
        }
    }

    public String get(String id) {
        UserRequest request = storage.getRequest(id);
        if (request == null) {return "Id does not exist.";}
        if (request.getState().equals("done")) {return request.getResult();} 
        else {return request.getState();}
    }

    public UserRequest getTest(String id) {
        return storage.getRequest(id); 
    }

    public boolean copy(UserRequest request) { 
        return storage.storeRequest(request.getId(), request);
    }
}