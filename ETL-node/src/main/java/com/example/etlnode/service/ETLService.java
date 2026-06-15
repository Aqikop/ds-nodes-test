package com.example.etlnode.service;

import com.example.etlnode.model.ETLModels.IngestRequest;
import com.example.etlnode.model.ETLModels.IngestResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

@Service
public class ETLService {

    private final RestTemplate restTemplate;
    private final String pythonApiBaseUrl;

    public ETLService(
            RestTemplate restTemplate,
            @Value("${python.etl.api.base-url:http://127.0.0.1:6000}") String pythonApiBaseUrl) {
        this.restTemplate = restTemplate;
        this.pythonApiBaseUrl = pythonApiBaseUrl;
    }
    // ── New: ingest dishes → Python FastAPI → Qdrant ───────────────────────────

    /**
     * Sends a list of dishes to the Python /ingest/json endpoint.
     * Returns 202 Accepted immediately; processing happens asynchronously.
     *
     * @param request IngestRequest containing a list of Dish objects
     * @return IngestResponse with status, queued count, and assigned IDs
     */
    public IngestResponse ingest(IngestRequest request) {
        return postJson("/ingest/json", request, IngestResponse.class);
    }

    // ── Shared HTTP helper ─────────────────────────────────────────────────────

    private <T> T postJson(String path, Object body, Class<T> responseType) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(body, headers);
        return restTemplate.postForObject(pythonApiBaseUrl + path, entity, responseType);
    }
}