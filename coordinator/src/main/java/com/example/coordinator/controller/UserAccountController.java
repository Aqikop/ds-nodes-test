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
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

@RestController
@RequestMapping("/api")
public class UserAccountController {
    private final ObjectMapper objectMapper;
    private final Path usersFile = Path.of("data", "users.json");
    private final Object lock = new Object();

    public UserAccountController(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper.copy().enable(SerializationFeature.INDENT_OUTPUT);
        ensureUsersFile();
    }

    @PostMapping("/login")
    public PublicUser login(@RequestBody LoginRequest request) {
        UserAccount user = readUsers().users.stream()
                .filter(account -> Objects.equals(account.username, clean(request.username)))
                .filter(account -> Objects.equals(account.password, request.password))
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED,
                        "Username or password is incorrect."
                ));

        return PublicUser.from(user);
    }

    @PostMapping("/register")
    @ResponseStatus(HttpStatus.CREATED)
    public PublicUser register(@RequestBody UserAccount request) {
        String username = clean(request.username);

        if (username.length() < 3) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Username must be at least 3 characters.");
        }

        if (request.password == null || request.password.length() < 4) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Password must be at least 4 characters.");
        }

        synchronized (lock) {
            UsersData data = readUsers();

            boolean exists = data.users.stream()
                    .anyMatch(user -> Objects.equals(user.username, username));

            if (exists) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "That username already exists.");
            }

            UserAccount user = new UserAccount();
            user.username = username;
            user.password = request.password;
            user.isAdmin = false;
            user.likes = safeList(request.likes);
            user.allergies = safeList(request.allergies);
            user.diet = cleanOrDefault(request.diet, "none");

            data.users.add(user);
            writeUsers(data);

            return PublicUser.from(user);
        }
    }

    @GetMapping("/users")
    public List<PublicUser> users() {
        return readUsers().users.stream()
                .map(PublicUser::from)
                .toList();
    }

    private void ensureUsersFile() {
        synchronized (lock) {
            if (Files.exists(usersFile)) {
                return;
            }

            try {
                Files.createDirectories(usersFile.getParent());

                try (InputStream input = getClass().getClassLoader().getResourceAsStream("static/users.json")) {
                    if (input != null) {
                        Files.copy(input, usersFile);
                        return;
                    }
                }

                UsersData data = new UsersData();
                UserAccount admin = new UserAccount();
                admin.username = "admin";
                admin.password = "admin123";
                admin.isAdmin = true;
                admin.likes = List.of();
                admin.allergies = List.of();
                admin.diet = "none";
                data.users.add(admin);
                writeUsers(data);
            } catch (IOException e) {
                throw new IllegalStateException("Could not create users file.", e);
            }
        }
    }

    private UsersData readUsers() {
        ensureUsersFile();

        synchronized (lock) {
            try {
                UsersData data = objectMapper.readValue(usersFile.toFile(), UsersData.class);
                if (data.users == null) {
                    data.users = new ArrayList<>();
                }
                return data;
            } catch (IOException e) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not read users file.");
            }
        }
    }

    private void writeUsers(UsersData data) {
        synchronized (lock) {
            try {
                objectMapper.writeValue(usersFile.toFile(), data);
            } catch (IOException e) {
                throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not save users file.");
            }
        }
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }

    private static String cleanOrDefault(String value, String fallback) {
        String cleanValue = clean(value);
        return cleanValue.isEmpty() ? fallback : cleanValue;
    }

    private static List<String> safeList(List<String> value) {
        if (value == null) {
            return new ArrayList<>();
        }

        return value.stream()
                .map(UserAccountController::clean)
                .filter(item -> !item.isEmpty())
                .toList();
    }

    public static class LoginRequest {
        public String username;
        public String password;
    }

    public static class UsersData {
        public List<UserAccount> users = new ArrayList<>();
    }

    public static class UserAccount {
        public String username;
        public String password;
        public boolean isAdmin;
        public List<String> likes = new ArrayList<>();
        public List<String> allergies = new ArrayList<>();
        public String diet = "none";
    }

    public static class PublicUser {
        public String username;
        public boolean isAdmin;
        public List<String> likes;
        public List<String> allergies;
        public String diet;

        public static PublicUser from(UserAccount user) {
            PublicUser publicUser = new PublicUser();
            publicUser.username = user.username;
            publicUser.isAdmin = user.isAdmin;
            publicUser.likes = safeList(user.likes);
            publicUser.allergies = safeList(user.allergies);
            publicUser.diet = cleanOrDefault(user.diet, "none");
            return publicUser;
        }
    }
}