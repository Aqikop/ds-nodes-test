package com.example.coordinator.service;

import org.springframework.stereotype.Component;

import org.springframework.scheduling.annotation.Scheduled;

import org.springframework.web.client.RestTemplate;

import org.springframework.web.util.UriComponentsBuilder;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;

import java.util.HashSet;

import java.util.concurrent.ThreadLocalRandom;

import com.example.coordinator.model.VoteRequest;
import com.example.coordinator.model.UserRequest;

@Component 
public class ConsensusService {
    private final RestTemplate restTemplate;
    private final ProcessingService processingService;
    private final RequestStorage storage;

    private final HashSet<String> nodesList = new HashSet<>();

    private String nodeId = "8080"; // do I need to sync???
    private boolean voted = false;
    
    public String nodeStatus = "follower"; // do I need to sync???
    public String leaderId = null; // do I need to sync???
    public int term = 0;

    public ConsensusService(RestTemplate restTemplate, 
            ProcessingService processingService, RequestStorage storage) {
        this.restTemplate = restTemplate;
        this.processingService = processingService;
        this.storage = storage;
        }

    public boolean vote(VoteRequest request) { 
        if (this.term <= request.getTerm()) {
            if(this.term < request.getTerm()) {
                this.term += 1;
                this.voted = false;
            }
            int candidateRequestCount = request.getRequestCount();
            if (candidateRequestCount >= 3 && !this.voted) {
                this.voted = true;
                this.nodeStatus = "follower";
                processingService.setIsLeader(false);
                return true;
                } 
            }
        return false;
    }

    public boolean ping(String id, int term) {
        if (term >= this.term) {
            this.leaderId = id;
            this.nodeStatus = "follower";
            processingService.setIsLeader(false);
            this.term = term;
            return true;
        } else {return false;}
    }

    public boolean join(String id) {
        if (nodeStatus.equals("leader")) {
            // try ping the node first??
            nodesList.add(id);
            //add the nodesList of storage
            // calling join of other nodes
            // send back node list to the new join
            // return an object contains all the needed data??
        } else {
            // try ping the node first??
            nodesList.add(id);
            //add the nodesList of storage
        }
        return true;
    }

    @Scheduled(fixedDelay = 1000)
    public void pingingThread() {
        if (nodeStatus.equals("leader")) {
            for (String node : nodesList) {
                try {
                    String targetUrl = "http://localhost:" + node + "/ping";
                    String urlTemplate = UriComponentsBuilder.fromHttpUrl(targetUrl)
                            .queryParam("id", nodeId)
                            .queryParam("term", this.term)
                            .encode()
                            .toUriString();

                    Boolean response = restTemplate.postForObject(urlTemplate, null, Boolean.class);
                    if (!response) {
                        nodeStatus = "follower"; 
                        processingService.setIsLeader(false);
                        }
                } catch (Exception e) {System.out.println("Broadcast failed.");}
            }
            System.out.println("Pinging other nodes.");
        }
    }

    @Scheduled(fixedDelay = 5000)
    public void scheduledTask() {
        System.out.println("Current Status: " + this.nodeStatus + " " + this.term);
        if (this.nodeStatus == "follower") {
            if (this.leaderId != null) {this.leaderId = null;}
            else {
                this.nodeStatus = "candidate";
                processingService.setIsLeader(false);
                while (this.nodeStatus.equals("candidate")) {
                    try {
                        long randomDelay = ThreadLocalRandom.current().nextLong(1000, 2000 + 1);
                        Thread.sleep(randomDelay);
                    } catch (Exception e) {}

                    if (!this.nodeStatus.equals("candidate")) {return;}

                    this.term = term + 1;
                    this.voted = false;
                    int vote = 1;
                    VoteRequest request = new VoteRequest();
                    request.setCandidateId(this.nodeId);
                    request.setRequestCount(4);
                    request.setTerm(this.term);

                    System.out.println("Start election " + this.term);
                    // check status again maybe??
                    for (String node : nodesList) {
                        try {
                            String targetUrl = "http://localhost:" + node + "/vote";
                            HttpHeaders headers = new HttpHeaders();
                            headers.setContentType(MediaType.APPLICATION_JSON);
                            HttpEntity<VoteRequest> entity = new HttpEntity<>(request, headers);
                            Boolean result = restTemplate.postForObject(targetUrl, entity, Boolean.class);
                            if (result) {vote = vote + 1;}
                        } catch (Exception e) {System.out.println("Ask for vote failed.");}
                    }

                    if (vote > ((nodesList.size() + 1) / 2) && this.nodeStatus.equals("candidate")) {
                        this.nodeStatus = "leader";
                        processingService.setIsLeader(true);
                        processingService.processingThread();
                        processingService.updateQueue();
                        System.out.println("Won");
                    }
                    else {System.out.println("Lost");}
                }
            }
        }
    }
}