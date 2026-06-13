package com.example.coordinator.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/dishes")
public class DishController {
    private final ObjectMapper objectMapper;
    private final Path dishesFile = Path.of("data", "dishes.json");
    private final Object lock = new Object();

    public DishController(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper.copy().enable(SerializationFeature.INDENT_OUTPUT);
        ensureDishesFile();
    }

    @GetMapping
    public List<Dish> dishes() {
        return readDishes().dishes;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Dish createDish(@RequestBody Dish request) {
        String name = clean(request.name);

        if (name.length() < 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Dish name is required.");
        }

        if (request.ingredients == null || safeList(request.ingredients).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "At least one ingredient is required.");
        }

        if (clean(request.cookingMethod).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Cooking method is required.");
        }

        synchronized (lock) {
            DishesData data = readDishes();

            Dish dish = new Dish();
            dish.id = UUID.randomUUID().toString();
            dish.name = name;
            dish.ingredients = safeList(request.ingredients);
            dish.cookingMethod = clean(request.cookingMethod);

            data.dishes.add(dish);
            writeDishes(data);

            return dish;
        }
    }

    private void ensureDishesFile() {
        synchronized (lock) {
            if (Files.exists(dishesFile)) {
                return;
            }

            try {
                Files.createDirectories(dishesFile.getParent());
                writeDishes(new DishesData());
            } catch (IOException e) {
                throw new IllegalStateException("Could not create dishes file.", e);
            }
        }
    }

    private DishesData readDishes() {
        ensureDishesFile();

        synchronized (lock) {
            try {
                DishesData data = objectMapper.readValue(dishesFile.toFile(), DishesData.class);
                if (data.dishes == null) {
                    data.dishes = new ArrayList<>();
                }
                return data;
            } catch (IOException e) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not read dishes file.");
            }
        }
    }

    private void writeDishes(DishesData data) {
        synchronized (lock) {
            try {
                objectMapper.writeValue(dishesFile.toFile(), data);
            } catch (IOException e) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not save dishes file.");
            }
        }
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }

    private static List<String> safeList(List<String> value) {
        if (value == null) {
            return new ArrayList<>();
        }

        return value.stream()
                .map(DishController::clean)
                .filter(item -> !item.isEmpty())
                .toList();
    }

    public static class DishesData {
        public List<Dish> dishes = new ArrayList<>();
    }

    public static class Dish {
        public String id;
        public String name;
        public List<String> ingredients = new ArrayList<>();
        public String cookingMethod;
    }
}