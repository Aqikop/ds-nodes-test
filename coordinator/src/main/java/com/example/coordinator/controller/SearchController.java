package com.example.coordinator.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.coordinator.service.CoordinatorService;
import com.example.coordinator.service.ProcessingService;
import com.example.coordinator.service.ConsensusService;
import com.example.coordinator.service.RequestStorage;

import com.example.coordinator.model.VoteRequest;
import com.example.coordinator.model.UserRequest;

import com.example.shared.model.LLMRequest;


@RestController
@RequestMapping("/")
public class SearchController {

    private final CoordinatorService coordinatorService;
    private final ConsensusService consensus;
    private final ProcessingService processingService;
    private final RequestStorage storage;

    public SearchController(CoordinatorService coordinatorService, ConsensusService consensus, 
            ProcessingService processingService, RequestStorage storage) {
        this.coordinatorService = coordinatorService;
        this.consensus = consensus;
        this.processingService = processingService;
        this.storage = storage;
    }

    @PostMapping("/search")
    public String search(@RequestBody LLMRequest request) {
        return coordinatorService.search(request);
    }

    @GetMapping("/get")
    public String get(@RequestParam String id) {
        return coordinatorService.get(id);
    } 

    @GetMapping("/gettest") // just for test TO DO: delete
    public UserRequest getTest(@RequestParam String id) {
        return coordinatorService.getTest(id);
    }

    @PostMapping("/copy") 
    public boolean copy(@RequestBody UserRequest request) { 
        storage.storeRequest(request.getId(), request);
        return true;
    }

    @PostMapping("/apply") 
    public boolean apply(@RequestParam String id, @RequestParam String type) { 
        return processingService.apply(id, type);
    }

    @PostMapping("/ping") 
    public boolean ping(@RequestParam String id, @RequestParam int term) { 
        return consensus.ping(id, term);
    }

    @PostMapping("/vote") 
    public boolean vote(@RequestBody VoteRequest request) { 
        return consensus.vote(request);
    }

    @PostMapping("/join") // return type of an object contains all data to sync??
    public boolean join(@RequestParam String id) { 
        return consensus.join(id);
    }
}