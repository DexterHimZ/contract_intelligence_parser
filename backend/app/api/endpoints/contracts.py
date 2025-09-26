from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Path
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List
import aiofiles
import os
import hashlib
from pathlib import Path as FilePath
from datetime import datetime
import logging

from app.models.contract import (
    Contract, ContractResponse, ContractListResponse,
    ProcessingStatus, ContractUpdate
)
from app.core.config import settings
from app.services.background_processor import background_processor
from app.services.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)
router = APIRouter()
pdf_processor = PDFProcessor()


@router.post("/contracts/upload", response_model=dict)
async def upload_contract(file: UploadFile = File(...)):
    """
    Upload a PDF contract for processing
    """
    try:
        # Validate file extension
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )

        # Check file size
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE / (1024*1024)}MB limit"
            )

        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Check if contract already exists
        existing = await Contract.find_one(Contract.hash == file_hash)
        if existing:
            return {
                "contract_id": str(existing.id),
                "message": "Contract already exists",
                "status": existing.status
            }

        # Save file to disk
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(settings.UPLOAD_DIR, f"{file_hash}_{file.filename}")

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)

        # Validate PDF
        is_valid, validation_message = pdf_processor.validate_pdf(file_path)
        if not is_valid:
            os.remove(file_path)  # Clean up invalid file
            raise HTTPException(
                status_code=400,
                detail=validation_message
            )

        # Create contract document
        contract = Contract(
            filename=file.filename,
            hash=file_hash,
            size_bytes=file_size,
            mime_type="application/pdf"
        )
        await contract.insert()

        # Start background processing
        background_processor.start_processing(str(contract.id), file_path)

        return {
            "contract_id": str(contract.id),
            "message": "Contract uploaded successfully and processing started",
            "status": contract.status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading contract: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}/status", response_model=dict)
async def get_processing_status(contract_id: str = Path(...)):
    """
    Check the processing status of a contract
    """
    contract = await Contract.get(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    return {
        "contract_id": str(contract.id),
        "status": contract.status,
        "progress": contract.processing_progress,
        "error_message": contract.processing.error_message if contract.status == ProcessingStatus.FAILED else None
    }


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(contract_id: str = Path(...)):
    """
    Get detailed contract data including extracted fields
    """
    contract = await Contract.get(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    return ContractResponse(
        id=str(contract.id),
        filename=contract.filename,
        status=contract.status,
        processing_progress=contract.processing_progress,
        uploaded_at=contract.uploaded_at,
        size_bytes=contract.size_bytes,
        mime_type=contract.mime_type,
        overall_score=contract.overall_score,
        confidence_summary=contract.confidence_summary,
        gaps=contract.gaps,
        fields=contract.fields,
        processing=contract.processing
    )


@router.get("/contracts", response_model=ContractListResponse)
async def list_contracts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[ProcessingStatus] = None,
    sort_by: str = Query("uploaded_at", regex="^(uploaded_at|overall_score|filename)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Get paginated list of contracts with filtering options
    """
    try:
        # Build query
        query = {}
        if status:
            query = Contract.status == status

        # Calculate pagination
        skip = (page - 1) * limit

        # Build sort
        sort_field = getattr(Contract, sort_by)
        sort_direction = -1 if sort_order == "desc" else 1

        # Get contracts
        if query:
            contracts = await Contract.find(query).sort(
                [(sort_field, sort_direction)]
            ).skip(skip).limit(limit).to_list()
            total = await Contract.find(query).count()
        else:
            contracts = await Contract.find_all().sort(
                [(sort_field, sort_direction)]
            ).skip(skip).limit(limit).to_list()
            total = await Contract.find_all().count()

        # Convert to response format
        contract_responses = []
        for contract in contracts:
            contract_responses.append(ContractResponse(
                id=str(contract.id),
                filename=contract.filename,
                status=contract.status,
                processing_progress=contract.processing_progress,
                uploaded_at=contract.uploaded_at,
                size_bytes=contract.size_bytes,
                mime_type=contract.mime_type,
                overall_score=contract.overall_score,
                confidence_summary=contract.confidence_summary,
                gaps=contract.gaps,
                fields=contract.fields,
                processing=contract.processing
            ))

        return ContractListResponse(
            total=total,
            page=page,
            limit=limit,
            contracts=contract_responses
        )

    except Exception as e:
        logger.error(f"Error listing contracts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}/download")
async def download_contract(contract_id: str = Path(...)):
    """
    Download the original contract PDF file
    """
    contract = await Contract.get(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Find the file
    file_path = os.path.join(settings.UPLOAD_DIR, f"{contract.hash}_{contract.filename}")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Contract file not found")

    return FileResponse(
        path=file_path,
        filename=contract.filename,
        media_type="application/pdf"
    )


@router.post("/contracts/{contract_id}/reprocess", response_model=dict)
async def reprocess_contract(
    contract_id: str = Path(...),
    use_ocr: bool = Query(True),
    use_llm: bool = Query(False),
    force: bool = Query(False)
):
    """
    Reprocess a contract with different settings
    """
    try:
        contract = await Contract.get(contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Check if already processing (unless force is True)
        if contract.status == ProcessingStatus.PROCESSING and not force:
            raise HTTPException(
                status_code=400,
                detail="Contract is already being processed"
            )

        # Start reprocessing
        await background_processor.reprocess_contract(
            contract_id, use_ocr=use_ocr, use_llm=use_llm
        )

        return {
            "contract_id": contract_id,
            "message": "Reprocessing started",
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing contract: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str = Path(...),
    update: ContractUpdate = ...
):
    """
    Update contract fields (for manual corrections)
    """
    try:
        contract = await Contract.get(contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Apply updates
        if update.fields is not None:
            contract.fields.update(update.fields)

        if update.gaps is not None:
            contract.gaps = update.gaps

        if update.confidence_summary is not None:
            contract.confidence_summary = update.confidence_summary

        if update.overall_score is not None:
            contract.overall_score = update.overall_score

        await contract.save()

        return ContractResponse(
            id=str(contract.id),
            filename=contract.filename,
            status=contract.status,
            processing_progress=contract.processing_progress,
            uploaded_at=contract.uploaded_at,
            size_bytes=contract.size_bytes,
            mime_type=contract.mime_type,
            overall_score=contract.overall_score,
            confidence_summary=contract.confidence_summary,
            gaps=contract.gaps,
            fields=contract.fields,
            processing=contract.processing
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contract: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contracts/{contract_id}", response_model=dict)
async def delete_contract(contract_id: str = Path(...)):
    """
    Delete a contract and its associated file
    """
    try:
        contract = await Contract.get(contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Delete file from disk
        file_path = os.path.join(settings.UPLOAD_DIR, f"{contract.hash}_{contract.filename}")
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete from database
        await contract.delete()

        return {
            "message": "Contract deleted successfully",
            "contract_id": contract_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contract: {e}")
        raise HTTPException(status_code=500, detail=str(e))