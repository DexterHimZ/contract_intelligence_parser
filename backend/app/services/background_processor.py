import asyncio
import logging
from typing import Optional
from pathlib import Path
from app.models.contract import Contract, ProcessingStatus
from app.services.contract_extractor import ContractExtractor
from app.services.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


class BackgroundProcessor:
    """Background processing service for contracts"""

    def __init__(self):
        self.extractor = ContractExtractor()
        self.pdf_processor = PDFProcessor()
        self.processing_tasks = {}

    async def process_contract_async(self, contract_id: str, file_path: str):
        """Process a contract asynchronously"""
        try:
            # Update status to processing
            contract = await Contract.get(contract_id)
            if not contract:
                logger.error(f"Contract {contract_id} not found")
                return

            contract.status = ProcessingStatus.PROCESSING
            contract.processing_progress = 10
            await contract.save()

            # Validate PDF
            is_valid, message = self.pdf_processor.validate_pdf(file_path)
            if not is_valid:
                await self._mark_failed(contract, message)
                return

            contract.processing_progress = 20
            await contract.save()

            # Extract and process contract data
            logger.info(f"Starting extraction for contract {contract_id}")
            result = await self.extractor.process_contract(file_path)

            contract.processing_progress = 80
            await contract.save()

            # Update contract with extracted data
            contract.text = result["text"]
            contract.fields = result["fields"]
            contract.gaps = result["gaps"]
            contract.confidence_summary = result["confidence_summary"]
            contract.overall_score = result["overall_score"]
            contract.processing = result["processing"]

            # Mark as completed
            contract.status = ProcessingStatus.COMPLETED
            contract.processing_progress = 100
            await contract.save()

            logger.info(f"Successfully processed contract {contract_id}")

        except Exception as e:
            logger.error(f"Error processing contract {contract_id}: {e}")
            await self._mark_failed(contract, str(e))

    async def _mark_failed(self, contract: Contract, error_message: str):
        """Mark contract processing as failed"""
        contract.status = ProcessingStatus.FAILED
        contract.processing.error_message = error_message
        contract.processing_progress = 0
        await contract.save()

    def start_processing(self, contract_id: str, file_path: str):
        """Start background processing for a contract"""
        task = asyncio.create_task(
            self.process_contract_async(contract_id, file_path)
        )
        self.processing_tasks[contract_id] = task
        return task

    async def reprocess_contract(
        self, contract_id: str,
        use_ocr: bool = True,
        use_llm: bool = False
    ):
        """Reprocess an existing contract with different settings"""
        try:
            contract = await Contract.get(contract_id)
            if not contract:
                raise ValueError(f"Contract {contract_id} not found")

            # Reset processing status
            contract.status = ProcessingStatus.PROCESSING
            contract.processing_progress = 0
            await contract.save()

            # Get file path with hash prefix (same format as upload)
            file_path = Path(f"/app/uploads/{contract.hash}_{contract.filename}")
            if not file_path.exists():
                raise FileNotFoundError(f"Contract file not found: {file_path}")

            # Reprocess with new settings
            await self.process_contract_async(str(contract_id), str(file_path))

        except Exception as e:
            logger.error(f"Error reprocessing contract {contract_id}: {e}")
            raise


# Global instance
background_processor = BackgroundProcessor()