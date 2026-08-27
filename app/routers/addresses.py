from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import Address, Contact
from app.schemas import AddressCreate, AddressRead, AddressReplace, ErrorResponse

router = APIRouter(prefix="/api/v1/contacts/{contact_id}/addresses", tags=["addresses"])

CONTACT_ID = Path(description="The contact that owns the address.", examples=[1], ge=1)
ADDRESS_ID = Path(description="Identifier returned when the address was created.", examples=[1], ge=1)

NOT_FOUND = {
    "model": ErrorResponse,
    "description": "No such contact, or the address does not belong to it.",
    "content": {"application/json": {"example": {"detail": "Address 7 not found on contact 1"}}},
}


def _get_contact_or_404(db: Session, contact_id: int) -> Contact:
    contact = crud.get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Contact {contact_id} not found")
    return contact


def _get_address_or_404(db: Session, contact_id: int, address_id: int) -> Address:
    _get_contact_or_404(db, contact_id)
    address = crud.get_address(db, contact_id, address_id)
    if address is None:
        # Deliberately the same 404 whether the address is missing or belongs to
        # someone else — the id space is not something to probe.
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Address {address_id} not found on contact {contact_id}"
        )
    return address


@router.get(
    "",
    response_model=list[AddressRead],
    operation_id="listContactAddresses",
    summary="List a contact's addresses",
    response_description="Every address on the contact, oldest first.",
    responses={status.HTTP_404_NOT_FOUND: NOT_FOUND},
)
def list_addresses(contact_id: int = CONTACT_ID, db: Session = Depends(get_db)) -> list[Address]:
    """
    List the addresses belonging to one contact.

    The same list is embedded in every contact response, so this endpoint is for
    clients that want the addresses on their own.
    """
    return _get_contact_or_404(db, contact_id).addresses


@router.post(
    "",
    response_model=AddressRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="addContactAddress",
    summary="Add an address to a contact",
    response_description="The stored address, including its new id.",
    responses={status.HTTP_404_NOT_FOUND: NOT_FOUND},
)
def add_address(
    payload: AddressCreate,
    contact_id: int = CONTACT_ID,
    db: Session = Depends(get_db),
) -> Address:
    """
    Add one address to a contact.

    A contact can hold any number of them, and `type` says which kind each one
    is — `Home`, `Work`, or `Other`. Anything else is rejected with `422`.
    """
    contact = _get_contact_or_404(db, contact_id)
    return crud.add_address(db, contact, payload)


@router.get(
    "/{address_id}",
    response_model=AddressRead,
    operation_id="getContactAddress",
    summary="Get one address",
    response_description="The requested address.",
    responses={status.HTTP_404_NOT_FOUND: NOT_FOUND},
)
def get_address(
    contact_id: int = CONTACT_ID,
    address_id: int = ADDRESS_ID,
    db: Session = Depends(get_db),
) -> Address:
    """Fetch a single address belonging to a contact."""
    return _get_address_or_404(db, contact_id, address_id)


@router.put(
    "/{address_id}",
    response_model=AddressRead,
    operation_id="replaceContactAddress",
    summary="Replace an address",
    response_description="The address after replacement.",
    responses={status.HTTP_404_NOT_FOUND: NOT_FOUND},
)
def replace_address(
    payload: AddressReplace,
    contact_id: int = CONTACT_ID,
    address_id: int = ADDRESS_ID,
    db: Session = Depends(get_db),
) -> Address:
    """
    Replace every field of one address.

    Like the contact `PUT`, optional fields left out of the body are cleared.
    """
    address = _get_address_or_404(db, contact_id, address_id)
    return crud.replace_address(db, address, payload)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteContactAddress",
    summary="Delete an address",
    response_description="Deleted; the response has no body.",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Deleted; the response has no body."},
        status.HTTP_404_NOT_FOUND: NOT_FOUND,
    },
)
def delete_address(
    contact_id: int = CONTACT_ID,
    address_id: int = ADDRESS_ID,
    db: Session = Depends(get_db),
) -> Response:
    """Remove one address. The contact and its other addresses are untouched."""
    crud.delete_address(db, _get_address_or_404(db, contact_id, address_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
