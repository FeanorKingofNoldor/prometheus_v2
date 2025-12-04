"""Prometheus v2 – Instrument ID to IBKR contract mapper.

This module provides translation between Prometheus instrument_id identifiers
and Interactive Brokers contract specifications.

The mapper:
- Queries the instruments table from the database
- Caches instrument metadata in memory
- Translates instrument_id to IBKR Stock contracts
- Handles refresh when new instruments are added
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ib_insync import Contract, Stock

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class InstrumentMetadata:
    """Metadata for a single instrument from the database.
    
    Attributes:
        instrument_id: Unique identifier (e.g. "AAPL.US")
        symbol: Trading symbol (e.g. "AAPL")
        exchange: Exchange code (e.g. "US", "SMART")
        currency: Currency code (e.g. "USD")
        asset_class: Asset class (e.g. "EQUITY", "OPTION")
    """
    
    instrument_id: str
    symbol: str
    exchange: str
    currency: str
    asset_class: str


class InstrumentMapper:
    """Maps Prometheus instrument_id to IBKR contracts.
    
    This class maintains an in-memory cache of instrument metadata loaded
    from the database and provides translation to IBKR contract objects.
    
    Usage:
        mapper = InstrumentMapper()
        mapper.load_instruments()  # Load from database
        
        contract = mapper.get_contract("AAPL.US")
        # Returns Stock("AAPL", "SMART", "USD")
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        """Initialize the mapper.
        
        Args:
            db_manager: Database manager instance. If None, uses default.
        """
        self._db = db_manager or get_db_manager()
        self._instruments: Dict[str, InstrumentMetadata] = {}
        self._loaded = False
    
    def load_instruments(self, force_reload: bool = False) -> None:
        """Load instrument metadata from the database.
        
        Args:
            force_reload: If True, reload even if already loaded.
        """
        if self._loaded and not force_reload:
            logger.debug("Instruments already loaded, skipping")
            return
        
        logger.info("Loading instruments from database")
        
        sql = """
            SELECT 
                instrument_id,
                symbol,
                exchange,
                currency,
                asset_class
            FROM instruments
            WHERE status = 'ACTIVE'
        """
        
        with self._db.get_runtime_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                
                self._instruments.clear()
                
                for row in rows:
                    instrument_id, symbol, exchange, currency, asset_class = row
                    
                    metadata = InstrumentMetadata(
                        instrument_id=instrument_id,
                        symbol=symbol,
                        exchange=exchange,
                        currency=currency,
                        asset_class=asset_class,
                    )
                    
                    self._instruments[instrument_id] = metadata
                
                self._loaded = True
                logger.info("Loaded %d instruments", len(self._instruments))
                
            finally:
                cur.close()
    
    def get_metadata(self, instrument_id: str) -> Optional[InstrumentMetadata]:
        """Get instrument metadata for a given instrument_id.
        
        Args:
            instrument_id: The instrument identifier (e.g. "AAPL.US")
            
        Returns:
            InstrumentMetadata if found, None otherwise.
        """
        if not self._loaded:
            self.load_instruments()
        
        return self._instruments.get(instrument_id)
    
    def get_contract(self, instrument_id: str) -> Contract:
        """Translate Prometheus instrument_id to IBKR Contract.
        
        Args:
            instrument_id: The instrument identifier (e.g. "AAPL.US")
            
        Returns:
            IBKR Contract object (currently only Stock supported)
            
        Raises:
            ValueError: If instrument not found or asset class not supported.
        """
        metadata = self.get_metadata(instrument_id)
        
        if metadata is None:
            # Fallback: try to parse instrument_id directly
            logger.warning(
                "Instrument %s not found in database, attempting direct parsing",
                instrument_id,
            )
            return self._parse_instrument_id_fallback(instrument_id)
        
        # Map asset class to IBKR contract type
        if metadata.asset_class == "EQUITY":
            # Use SMART routing for US equities
            exchange = "SMART" if metadata.exchange == "US" else metadata.exchange
            
            contract = Stock(
                symbol=metadata.symbol,
                exchange=exchange,
                currency=metadata.currency,
            )
            
            logger.debug(
                "Mapped %s -> Stock(%s, %s, %s)",
                instrument_id,
                metadata.symbol,
                exchange,
                metadata.currency,
            )
            
            return contract
        else:
            raise ValueError(
                f"Asset class {metadata.asset_class} not yet supported for IBKR mapping"
            )
    
    def _parse_instrument_id_fallback(self, instrument_id: str) -> Contract:
        """Fallback parser when instrument not found in database.
        
        Assumes format is "SYMBOL.EXCHANGE" (e.g. "AAPL.US")
        """
        parts = instrument_id.split(".")
        
        if len(parts) >= 2:
            symbol = parts[0].upper()
            exchange_hint = parts[1].upper()
            
            # Map exchange hint to IBKR exchange
            if exchange_hint == "US":
                exchange = "SMART"
                currency = "USD"
            else:
                exchange = exchange_hint
                currency = "USD"  # Assume USD for now
            
            logger.info(
                "Fallback parsing: %s -> Stock(%s, %s, %s)",
                instrument_id,
                symbol,
                exchange,
                currency,
            )
            
            return Stock(symbol, exchange, currency)
        else:
            # Last resort: assume it's just a symbol
            logger.warning(
                "Could not parse instrument_id %s, treating as US equity symbol",
                instrument_id,
            )
            return Stock(instrument_id.upper(), "SMART", "USD")
    
    def refresh(self) -> None:
        """Reload instruments from database.
        
        This is useful when new instruments are added during runtime.
        """
        self.load_instruments(force_reload=True)
    
    def get_instrument_count(self) -> int:
        """Return the number of loaded instruments."""
        return len(self._instruments)


# Global singleton instance for convenience
_global_mapper: Optional[InstrumentMapper] = None


def get_instrument_mapper(db_manager: Optional[DatabaseManager] = None) -> InstrumentMapper:
    """Get the global instrument mapper instance.
    
    Args:
        db_manager: Optional database manager. Only used on first call.
        
    Returns:
        Global InstrumentMapper singleton.
    """
    global _global_mapper
    
    if _global_mapper is None:
        _global_mapper = InstrumentMapper(db_manager)
        _global_mapper.load_instruments()
    
    return _global_mapper


__all__ = [
    "InstrumentMetadata",
    "InstrumentMapper",
    "get_instrument_mapper",
]
