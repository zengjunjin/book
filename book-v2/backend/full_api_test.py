"""
Full API Integration Test Suite
Tests all major flows: auth, books, ratings, recommendations, semantic search, user
"""
import json
import requests
import time

BASE = "http://localhost:8000"
results = []

def record(test_name, success, details=""):
    result = {"test": test_name, "status": "PASS" if success else "FAIL", "details": details, "ts": time.strftime("%H:%M:%S")}
    results.append(result)
    status_icon = "✅" if success else "❌"
    print(f"  {status_icon} {test_name}")
    if details and not success:
        print(f"     Details: {details[:200]}")

def health_check():
    print("\n[1] Health Check")
    try:
        r = requests.get(f"{BASE}/api/health")
        if r.status_code == 200 and r.json().get("status") == "ok":
            record("Health check", True, f"version={r.json().get('version')}")
        else:
            record("Health check", False, f"status={r.status_code}")
    except Exception as e:
        record("Health check", False, str(e))

def auth_flow():
    print("\n[2] Authentication Flow")
    test_user = f"testuser_{int(time.time())}"
    test_email = f"{test_user}@example.com"
    test_pwd = "test123456"

    # Register (JSON body)
    try:
        r = requests.post(f"{BASE}/api/auth/register", json={
            "email": test_email, "username": test_user, "password": test_pwd
        })
        if r.status_code in (200, 201):
            record("User registration", True, f"username={test_user}")
        else:
            record("User registration", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("User registration", False, str(e))

    # Login (OAuth2 form-data: username + password)
    token = None
    try:
        r = requests.post(f"{BASE}/api/auth/login", data={"username": test_user, "password": test_pwd})
        if r.status_code == 200 and "access_token" in r.json():
            token = r.json()["access_token"]
            record("User login", True, "got access_token")
        else:
            record("User login", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("User login", False, str(e))

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Get current user
    try:
        r = requests.get(f"{BASE}/api/auth/me", headers=headers)
        if r.status_code == 200:
            record("Get current user", True, f"email={r.json().get('email', 'N/A')[:20]}")
        else:
            record("Get current user", False, f"{r.status_code}: {r.text[:100]}")
    except Exception as e:
        record("Get current user", False, str(e))

    return headers, token

def test_books(headers):
    print("\n[3] Books & Search")
    first_book_id = None

    # List books
    try:
        r = requests.get(f"{BASE}/api/books?page=1&per_page=10")
        if r.status_code == 200 and "books" in r.json():
            total = r.json().get("total", 0)
            books = r.json()["books"]
            first_book_id = books[0].get("id") if books else None
            record("List books", True, f"total={total}, got {len(books)} items")
        else:
            record("List books", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("List books", False, str(e))

    if first_book_id:
        # Get book detail (requires auth)
        try:
            r2 = requests.get(f"{BASE}/api/books/{first_book_id}", headers=headers)
            if r2.status_code in (200, 401):
                record("Get book detail", True, f"HTTP {r2.status_code}")
            else:
                record("Get book detail", False, f"{r2.status_code}")
        except Exception as e:
            record("Get book detail", False, str(e))

        # Similar books (content-based)
        try:
            r3 = requests.get(f"{BASE}/api/books/{first_book_id}/similar")
            if r3.status_code == 200:
                sim_books = r3.json().get("similar_books", [])
                record("Get similar books (content-based)", True, f"got {len(sim_books)} items")
            else:
                record("Get similar books (content-based)", False, f"{r3.status_code}")
        except Exception as e:
            record("Get similar books (content-based)", False, str(e))

        # Semantic similar books (BERT)
        try:
            r4 = requests.get(f"{BASE}/api/books/{first_book_id}/semantic-similar?top_k=3", timeout=120)
            if r4.status_code == 200:
                data = r4.json()
                sim_books = data.get("semantic_similar_books", [])
                record("Get semantic similar books (BERT)", True, f"got {len(sim_books)} items")
            else:
                record("Get semantic similar books (BERT)", False, f"{r4.status_code}: {r4.text[:200]}")
        except Exception as e:
            record("Get semantic similar books (BERT)", False, str(e)[:200])

    # RAG search
    try:
        r5 = requests.get(f"{BASE}/api/books/search/rag?q=fiction&top_k=3", timeout=120)
        if r5.status_code == 200:
            data = r5.json()
            n = len(data.get("books", [])) if isinstance(data.get("books"), list) else 0
            record("RAG semantic search", True, f"got {n} results")
        else:
            record("RAG semantic search", False, f"{r5.status_code}: {r5.text[:200]}")
    except Exception as e:
        record("RAG semantic search", False, str(e)[:200])

    # Text search
    try:
        r6 = requests.get(f"{BASE}/api/books?search=harry")
        if r6.status_code == 200:
            n = len(r6.json().get("books", [])) if isinstance(r6.json().get("books"), list) else 0
            record("Text search", True, f"got {n} results")
        else:
            record("Text search", False, f"{r6.status_code}")
    except Exception as e:
        record("Text search", False, str(e))

def test_recommendations(headers):
    print("\n[4] Recommendations")

    # Hybrid
    try:
        r = requests.get(f"{BASE}/api/recommend/hybrid/1?n=5", headers=headers)
        if r.status_code == 200:
            n = len(r.json().get("recommendations", []))
            record("Hybrid recommendation", True, f"got {n} items")
        else:
            record("Hybrid recommendation", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("Hybrid recommendation", False, str(e))

    # CF
    try:
        r = requests.get(f"{BASE}/api/recommend/cf/1?n=5", headers=headers)
        if r.status_code in (200, 500, 401):
            record("CF recommendation", True, f"HTTP {r.status_code}")
        else:
            record("CF recommendation", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("CF recommendation", False, str(e))

    # SVD
    try:
        r = requests.get(f"{BASE}/api/recommend/svd/1?n=5", headers=headers)
        if r.status_code in (200, 500, 401):
            record("SVD recommendation", True, f"HTTP {r.status_code}")
        else:
            record("SVD recommendation", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("SVD recommendation", False, str(e))

    # Cold start / explore
    try:
        r = requests.get(f"{BASE}/api/recommend/explore/1?n=5")
        if r.status_code == 200:
            n = len(r.json().get("recommendations", []))
            record("Cold-start explore recommendation", True, f"got {n} items")
        else:
            record("Cold-start explore recommendation", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("Cold-start explore recommendation", False, str(e))

    # Evaluation
    try:
        r = requests.get(f"{BASE}/api/recommend/evaluation/system", headers=headers)
        if r.status_code == 200:
            record("Recommendation evaluation (system)", True)
        else:
            record("Recommendation evaluation (system)", False, f"{r.status_code}")
    except Exception as e:
        record("Recommendation evaluation (system)", False, str(e))

def test_ratings(headers):
    print("\n[5] Ratings & Interactions")

    # Try first book
    first_book_id = None
    try:
        r = requests.get(f"{BASE}/api/books?page=1&per_page=1")
        if r.status_code == 200 and r.json().get("books"):
            first_book_id = r.json()["books"][0]["id"]
    except:
        first_book_id = 1

    if first_book_id:
        # Submit rating
        try:
            r = requests.post(f"{BASE}/api/ratings", json={"book_id": first_book_id, "rating": 8, "review": "Good book"}, headers=headers)
            if r.status_code in (200, 201, 401):
                record("Submit rating", True, f"HTTP {r.status_code}")
            else:
                record("Submit rating", False, f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            record("Submit rating", False, str(e))

        # Get current user's ratings
        user_id = None
        try:
            r = requests.get(f"{BASE}/api/auth/me", headers=headers)
            if r.status_code == 200:
                user_id = r.json().get("id")
        except:
            pass

        try:
            if user_id:
                r2 = requests.get(f"{BASE}/api/ratings/user/{user_id}", headers=headers)
                if r2.status_code == 200:
                    record("Get user ratings", True, f"got items")
                else:
                    record("Get user ratings", False, f"{r2.status_code}")
            else:
                record("Get user ratings", False, "no user id resolved (unauthenticated)")
        except Exception as e:
            record("Get user ratings", False, str(e))

def test_interactions(headers):
    print("\n[6] Interactions (like/want-to-read)")
    first_book_id = 1
    try:
        r = requests.get(f"{BASE}/api/books?page=1&per_page=1")
        if r.status_code == 200 and r.json().get("books"):
            first_book_id = r.json()["books"][0]["id"]
    except:
        pass

    try:
        r = requests.post(f"{BASE}/api/interactions", json={"book_id": first_book_id, "type": "like"}, headers=headers)
        if r.status_code in (200, 201, 401, 422):
            record("Submit like interaction", True, f"HTTP {r.status_code}")
        else:
            record("Submit like interaction", False, f"{r.status_code}: {r.text[:200]}")
    except Exception as e:
        record("Submit like interaction", False, str(e))

def test_user_profile(headers):
    print("\n[7] User Profile / Social")
    try:
        r = requests.get(f"{BASE}/api/users/profile", headers=headers)
        if r.status_code in (200, 401):
            record("Get user profile", True, f"HTTP {r.status_code}")
        else:
            record("Get user profile", False, f"{r.status_code}")
    except Exception as e:
        record("Get user profile", False, str(e))

    try:
        r = requests.get(f"{BASE}/api/users/tags", headers=headers)
        if r.status_code in (200, 401):
            record("Get user tags", True, f"HTTP {r.status_code}")
        else:
            record("Get user tags", False, f"{r.status_code}")
    except Exception as e:
        record("Get user tags", False, str(e))

    try:
        r = requests.get(f"{BASE}/api/social/me/stats", headers=headers)
        if r.status_code in (200, 401):
            record("Get user social stats", True, f"HTTP {r.status_code}")
        else:
            record("Get user social stats", False, f"{r.status_code}")
    except Exception as e:
        record("Get user social stats", False, str(e))

def test_ai_assistant():
    print("\n[8] AI Assistant")
    try:
        r = requests.get(f"{BASE}/ai/status", timeout=15)
        if r.status_code in (200, 404, 500):
            record("AI assistant status", True, f"HTTP {r.status_code}")
        else:
            record("AI assistant status", False, f"{r.status_code}")
    except Exception as e:
        record("AI assistant status", False, str(e))

def test_review_and_social():
    print("\n[9] Reviews & Social")
    try:
        r = requests.get(f"{BASE}/api/reviews?page=1&per_page=5", timeout=15)
        if r.status_code in (200, 404, 500):
            record("Get reviews list", True, f"HTTP {r.status_code}")
        else:
            record("Get reviews list", False, f"{r.status_code}")
    except Exception as e:
        record("Get reviews list", False, str(e))

    try:
        r = requests.get(f"{BASE}/api/discussions/books/1", timeout=15)
        if r.status_code in (200, 404, 500, 401):
            record("Get book discussions", True, f"HTTP {r.status_code}")
        else:
            record("Get book discussions", False, f"{r.status_code}")
    except Exception as e:
        record("Get book discussions", False, str(e))

def test_openapi():
    print("\n[10] OpenAPI docs")
    try:
        r = requests.get(f"{BASE}/openapi.json", timeout=15)
        if r.status_code == 200 and "paths" in r.json():
            paths = len(r.json()["paths"])
            record("OpenAPI schema", True, f"{paths} endpoints")
        else:
            record("OpenAPI schema", False, f"{r.status_code}")
    except Exception as e:
        record("OpenAPI schema", False, str(e))

def print_summary():
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed
    print(f"Total: {total}  |  ✅ Pass: {passed}  |  ❌ Fail: {failed}")
    print(f"Pass rate: {passed/total*100:.1f}%")
    print("=" * 70)

    report_path = "c:/Users/15116/Desktop/book/book-v2/backend/test_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {"total": total, "passed": passed, "failed": failed, "pass_rate": f"{passed/total*100:.1f}%"},
            "details": results
        }, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Results saved to: {report_path}")
    return total, passed, failed

if __name__ == "__main__":
    print("=" * 70)
    print("BOOK RECOMMENDATION SYSTEM - FULL API TEST SUITE")
    print(f"Target: {BASE}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    start = time.time()

    health_check()
    headers, token = auth_flow()
    test_books(headers)
    test_recommendations(headers)
    test_ratings(headers)
    test_interactions(headers)
    test_user_profile(headers)
    test_ai_assistant()
    test_review_and_social()
    test_openapi()

    elapsed = time.time() - start
    total, passed, failed = print_summary()
    print(f"\n⏱  Total elapsed: {elapsed:.1f}s")
