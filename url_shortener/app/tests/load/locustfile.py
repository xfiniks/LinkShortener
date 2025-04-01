from locust import HttpUser, task, between
import random
import string
import json

class URLShortenerUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login and get token
        self.login()
        
        # Store some short codes we've created
        self.short_codes = []
        
        # Create some initial links
        for i in range(3):
            response = self.client.post(
                "/links/shorten",
                json={"original_url": f"https://example.com/page{i}"},
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if response.status_code == 201:
                self.short_codes.append(response.json()["short_code"])
    
    def login(self):
        # Register a user with unique username
        username = f"loadtest_{random.randint(1000, 9999)}"
        self.client.post(
            "/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "password123"
            }
        )
        
        # Login to get token
        response = self.client.post(
            "/auth/token",
            data={
                "username": username,
                "password": "password123"
            }
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            self.token = None
    
    @task(3)
    def create_short_link(self):
        # Generate a random URL
        random_path = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        original_url = f"https://example.com/{random_path}"
        
        # Create a short link
        response = self.client.post(
            "/links/shorten",
            json={"original_url": original_url},
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if response.status_code == 201:
            new_code = response.json()["short_code"]
            self.short_codes.append(new_code)
            
            if len(self.short_codes) > 20:
                self.short_codes = self.short_codes[-20:]
    
    @task(10)
    def access_short_link(self):
        # Access one of our short links
        if self.short_codes:
            short_code = random.choice(self.short_codes)
            self.client.get(f"/{short_code}", allow_redirects=False)
    
    @task(1)
    def get_link_info(self):
        # Get info about one of our short links
        if self.short_codes:
            short_code = random.choice(self.short_codes)
            self.client.get(
                f"/links/{short_code}",
                headers={"Authorization": f"Bearer {self.token}"}
            )
    
    @task(1)
    def get_link_stats(self):
        # Get stats for one of our short links
        if self.short_codes:
            short_code = random.choice(self.short_codes)
            self.client.get(
                f"/links/{short_code}/stats",
                headers={"Authorization": f"Bearer {self.token}"}
            )
    
    @task(1)
    def update_link(self):
        # Update one of our short links
        if self.short_codes:
            short_code = random.choice(self.short_codes)
            random_path = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            new_url = f"https://example.com/updated/{random_path}"
            
            self.client.put(
                f"/links/{short_code}",
                json={"original_url": new_url},
                headers={"Authorization": f"Bearer {self.token}"}
            )
    
    @task(1)
    def delete_link(self):
        # Delete one of our short links
        if self.short_codes and len(self.short_codes) > 5:
            short_code = random.choice(self.short_codes)
            self.client.delete(
                f"/links/{short_code}",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if short_code in self.short_codes:
                self.short_codes.remove(short_code)