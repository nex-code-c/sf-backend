import base64

from app.schemas import MAX_PHOTO_BYTES, MAX_PHOTO_LENGTH

BASE = "/api/v1/contacts"
PHOTO = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf"
    "FcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
HOME = {"type": "Home", "street": "12 Ockham Rd", "city": "London", "country": "UK"}
WORK = {"type": "Work", "street": "1 Market St", "city": "San Francisco", "state": "CA"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "sqlite"


def test_create_contact(client, payload):
    response = client.post(BASE, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["email"] == "ada@example.com"
    assert body["full_name"] == "Ada Lovelace"
    assert body["created_at"] and body["updated_at"]


def test_create_requires_valid_email(client, payload):
    response = client.post(BASE, json={**payload, "email": "not-an-email"})
    assert response.status_code == 422


def test_create_requires_names(client, payload):
    response = client.post(BASE, json={**payload, "first_name": ""})
    assert response.status_code == 422


def test_duplicate_email_conflicts(client, payload):
    assert client.post(BASE, json=payload).status_code == 201
    response = client.post(BASE, json={**payload, "email": "ADA@example.com"})
    assert response.status_code == 409


def test_get_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.get(f"{BASE}/{contact_id}")
    assert response.status_code == 200
    assert response.json()["id"] == contact_id


def test_get_missing_contact_returns_404(client):
    assert client.get(f"{BASE}/9999").status_code == 404


def test_list_pagination_and_total(client, payload):
    for index in range(5):
        client.post(BASE, json={**payload, "email": f"user{index}@example.com"})

    response = client.get(BASE, params={"limit": 2, "offset": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 2


def test_list_search(client, payload):
    client.post(BASE, json=payload)
    client.post(
        BASE,
        json={**payload, "first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com", "company": "US Navy"},
    )

    hits = client.get(BASE, params={"search": "hopper"}).json()
    assert hits["total"] == 1
    assert hits["items"][0]["last_name"] == "Hopper"

    by_company = client.get(BASE, params={"search": "navy"}).json()
    assert by_company["total"] == 1

    misses = client.get(BASE, params={"search": "nobody"}).json()
    assert misses["total"] == 0


def test_list_sorting(client, payload):
    client.post(BASE, json={**payload, "last_name": "Zhang", "email": "z@example.com"})
    client.post(BASE, json={**payload, "last_name": "Adams", "email": "a@example.com"})

    names = [
        item["last_name"]
        for item in client.get(BASE, params={"sort_by": "last_name", "order": "asc"}).json()["items"]
    ]
    assert names == ["Adams", "Zhang"]


def test_list_rejects_bad_sort_field(client):
    assert client.get(BASE, params={"sort_by": "; DROP TABLE contacts"}).status_code == 422


def test_patch_updates_only_sent_fields(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"phone": "+1-000-000-0000"})
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+1-000-000-0000"
    assert body["first_name"] == "Ada"
    assert body["company"] == "Analytical Engines"


def test_patch_duplicate_email_conflicts(client, payload):
    first = client.post(BASE, json=payload).json()["id"]
    client.post(BASE, json={**payload, "email": "grace@example.com"})
    response = client.patch(f"{BASE}/{first}", json={"email": "grace@example.com"})
    assert response.status_code == 409


def test_patch_same_email_is_allowed(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"email": payload["email"]})
    assert response.status_code == 200


def test_put_replaces_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["company"] is None  # omitted fields are cleared by PUT


def test_put_missing_contact_returns_404(client):
    response = client.put(
        f"{BASE}/9999",
        json={"first_name": "A", "last_name": "B", "email": "ab@example.com"},
    )
    assert response.status_code == 404


def test_photo_round_trips_through_create_and_get(client, payload):
    created = client.post(BASE, json={**payload, "photo": PHOTO})
    assert created.status_code == 201
    assert created.json()["photo"] == PHOTO

    fetched = client.get(f"{BASE}/{created.json()['id']}")
    assert fetched.json()["photo"] == PHOTO


def test_photo_defaults_to_null(client, payload):
    assert client.post(BASE, json=payload).json()["photo"] is None


def test_patch_leaves_photo_alone(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"job_title": "Countess"})
    assert response.json()["photo"] == PHOTO


def test_patch_can_clear_photo(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"photo": None})
    assert response.json()["photo"] is None


def test_photo_must_be_an_image_data_url(client, payload):
    for bad in ["hello", "https://example.com/ada.png", "data:text/html;base64,PHNjcmlwdD4="]:
        response = client.post(BASE, json={**payload, "photo": bad})
        assert response.status_code == 422, bad


def test_photo_must_be_decodable_base64(client, payload):
    """Looking like base64 is not enough -- these all decode to nothing valid."""
    for bad in ["data:image/png;base64,A", "data:image/png;base64,AAAAA"]:
        response = client.post(BASE, json={**payload, "photo": bad})
        assert response.status_code == 422, bad


def test_photo_has_a_size_ceiling(client, payload):
    oversized = "data:image/png;base64," + "A" * MAX_PHOTO_LENGTH
    assert client.post(BASE, json={**payload, "photo": oversized}).status_code == 422


def test_photo_ceiling_is_measured_on_the_decoded_bytes(client, payload):
    """A string inside the character cap can still decode past the byte cap."""
    prefix = "data:image/jpeg;base64,"
    photo = prefix + "A" * (MAX_PHOTO_LENGTH - len(prefix))

    # Short enough to clear the cheap length check, so only decoding catches it.
    assert len(photo) <= MAX_PHOTO_LENGTH
    assert len(base64.b64decode(photo.removeprefix(prefix))) > MAX_PHOTO_BYTES

    assert client.post(BASE, json={**payload, "photo": photo}).status_code == 422


def test_patch_validates_the_photo_too(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    assert client.patch(f"{BASE}/{contact_id}", json={"photo": "nope"}).status_code == 422


def test_put_clears_an_omitted_photo(client, payload):
    """PUT is a full replace: a client that drops `photo` loses the photo.

    The web form guards against this by resubmitting the current photo; this
    test pins the API contract that makes that necessary.
    """
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]

    replaced = client.put(f"{BASE}/{contact_id}", json=payload)
    assert replaced.json()["photo"] is None

    kept = client.put(f"{BASE}/{contact_id}", json={**payload, "photo": PHOTO})
    assert kept.json()["photo"] == PHOTO


def test_create_contact_with_addresses(client, payload):
    response = client.post(BASE, json={**payload, "addresses": [HOME, WORK]})
    assert response.status_code == 201

    addresses = response.json()["addresses"]
    assert [address["type"] for address in addresses] == ["Home", "Work"]
    assert addresses[0]["street"] == "12 Ockham Rd"
    assert all(address["id"] > 0 for address in addresses)


def test_addresses_default_to_empty(client, payload):
    assert client.post(BASE, json=payload).json()["addresses"] == []


def test_address_type_is_constrained(client, payload):
    response = client.post(BASE, json={**payload, "addresses": [{**HOME, "type": "Beach"}]})
    assert response.status_code == 422


def test_address_type_defaults_to_home(client, payload):
    response = client.post(BASE, json={**payload, "addresses": [{"city": "London"}]})
    assert response.json()["addresses"][0]["type"] == "Home"


def test_addresses_nest_under_the_contact_everywhere(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [HOME]}).json()["id"]

    assert client.get(f"{BASE}/{contact_id}").json()["addresses"][0]["city"] == "London"
    listed = client.get(BASE).json()["items"][0]
    assert listed["addresses"][0]["city"] == "London"


def test_put_replaces_the_whole_address_set(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [HOME]}).json()["id"]

    replaced = client.put(f"{BASE}/{contact_id}", json={**payload, "addresses": [WORK]})
    assert [address["type"] for address in replaced.json()["addresses"]] == ["Work"]

    cleared = client.put(f"{BASE}/{contact_id}", json=payload)
    assert cleared.json()["addresses"] == []


def test_patch_leaves_addresses_alone_unless_sent(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [HOME]}).json()["id"]

    untouched = client.patch(f"{BASE}/{contact_id}", json={"job_title": "Countess"})
    assert len(untouched.json()["addresses"]) == 1

    emptied = client.patch(f"{BASE}/{contact_id}", json={"addresses": []})
    assert emptied.json()["addresses"] == []


def test_address_crud_through_the_nested_routes(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    addresses_url = f"{BASE}/{contact_id}/addresses"

    created = client.post(addresses_url, json=HOME)
    assert created.status_code == 201
    address_id = created.json()["id"]

    assert client.get(addresses_url).json()[0]["id"] == address_id
    assert client.get(f"{addresses_url}/{address_id}").json()["street"] == "12 Ockham Rd"

    updated = client.put(f"{addresses_url}/{address_id}", json=WORK)
    assert updated.json()["type"] == "Work"
    assert updated.json()["city"] == "San Francisco"

    assert client.delete(f"{addresses_url}/{address_id}").status_code == 204
    assert client.get(addresses_url).json() == []


def test_address_routes_404_on_a_foreign_address(client, payload):
    mine = client.post(BASE, json=payload).json()["id"]
    theirs = client.post(BASE, json={**payload, "email": "grace@example.com"}).json()["id"]
    address_id = client.post(f"{BASE}/{mine}/addresses", json=HOME).json()["id"]

    # The address exists, but not on that contact.
    assert client.get(f"{BASE}/{theirs}/addresses/{address_id}").status_code == 404
    assert client.delete(f"{BASE}/{theirs}/addresses/{address_id}").status_code == 404
    assert client.get(f"{BASE}/9999/addresses").status_code == 404


def test_deleting_a_contact_takes_its_addresses(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [HOME, WORK]}).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204
    assert client.get(f"{BASE}/{contact_id}/addresses").status_code == 404


def test_delete_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204
    assert client.get(f"{BASE}/{contact_id}").status_code == 404
    assert client.delete(f"{BASE}/{contact_id}").status_code == 404


def test_root_lists_entrypoints(client):
    body = client.get("/").json()
    assert body["contacts"] == BASE
