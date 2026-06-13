package com.example.coordinator.model;

public class VoteRequest {
    public int term;
    public String candidateId;
    public int requestCount;

    public VoteRequest() {}

    public int getTerm() {return term;}
    public void setTerm(int term) {this.term = term;}

    public String getCandidateId() {return candidateId;}
    public void setCandidateId(String candidateId) {this.candidateId = candidateId;}

    public int getRequestCount() {return requestCount;}
    public void setRequestCount(int requestCount) {this.requestCount = requestCount;}
}