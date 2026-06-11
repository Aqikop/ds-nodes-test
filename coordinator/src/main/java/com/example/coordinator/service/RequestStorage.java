package com.example.coordinator.service;

import org.springframework.stereotype.Component;

import org.springframework.web.client.RestTemplate;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;

import java.util.concurrent.ConcurrentHashMap;

import java.util.List;
import java.util.Set;
import java.util.HashSet;

import com.example.coordinator.model.UserRequest;

@Component 
public class RequestStorage {

    private final RestTemplate restTemplate;
    private final HashSet<String> nodesList;
    private final ConcurrentHashMap<String, UserRequest> requestStatus;

    public RequestStorage(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
        this.nodesList = new HashSet<>();
        this.requestStatus = new ConcurrentHashMap<>();
    }
    // method to change nodelist, control by consensus service

    public UserRequest getRequest(String id) {
        return requestStatus.get(id);
    }

    public Set<String> getRequestList() {
        return requestStatus.keySet();
    }

    public boolean storeRequest(String id, UserRequest request) {
        try {
            requestStatus.put(id, request);
            return true;
        } catch (Exception e) {return false;}
    }

    public void deleteRequest(String id) {
        requestStatus.remove(id);
    }

    public void broadCastCopy(UserRequest request) { 
        // only leaders
        for (String node : nodesList) {
            try {
                String targetUrl = "http://localhost:" + node + "/copy";
                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.APPLICATION_JSON);
                HttpEntity<UserRequest> entity = new HttpEntity<>(request, headers);
                Boolean result = restTemplate.postForObject(targetUrl, entity, Boolean.class);
                if (result) {System.out.println("Broadcast request done.");}
            } catch (Exception e) {System.out.println("Broadcast request failed.");}
        }
    }
}