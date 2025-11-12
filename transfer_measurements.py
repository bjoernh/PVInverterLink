#!/usr/bin/env python3
"""
Transfer measurements between TimescaleDB instances for testing purposes.

This script transfers data from a source database to a target database.
By default, it only transfers measurements. Use --users and --inverters flags to also
transfer users and inverters.

Usage:
    # Transfer only measurements (requires users/inverters to exist in target)
    ENV_FILE=.env uv run python transfer_measurements.py \\
        --source-url "postgresql+asyncpg://user:pass@source:5432/db" \\
        --target-url "postgresql+asyncpg://user:pass@target:5432/db" \\
        --start-date "2025-10-31" \\
        --end-date "2025-10-31"

    # Transfer users, inverters, and measurements
    ENV_FILE=.env uv run python transfer_measurements.py \\
        --source-url "postgresql+asyncpg://user:pass@source:5432/db" \\
        --target-url "postgresql+asyncpg://user:pass@target:5432/db" \\
        --start-date "2025-10-31" \\
        --end-date "2025-10-31" \\
        --users --inverters \\
        --dry-run
"""

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()


class MeasurementTransfer:
    """Handles transfer of measurements between TimescaleDB instances."""

    def __init__(
        self,
        source_url: str,
        target_url: str,
        start_date: date,
        end_date: date,
        batch_size: int = 1000,
        dry_run: bool = False,
        transfer_users: bool = False,
        transfer_inverters: bool = False,
    ):
        self.source_url = source_url
        self.target_url = target_url
        self.start_date = start_date
        self.end_date = end_date
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.should_transfer_users = transfer_users
        self.should_transfer_inverters = transfer_inverters

        # ID mappings: source_id -> target_id
        self.user_id_map: dict[int, int] = {}
        self.inverter_id_map: dict[int, int] = {}

        # Engines and sessions
        self.source_engine = None
        self.target_engine = None
        self.source_sessionmaker = None
        self.target_sessionmaker = None

    async def init_connections(self):
        """Initialize database connections."""
        logger.info("Initializing database connections")
        self.source_engine = create_async_engine(self.source_url, echo=False)
        self.target_engine = create_async_engine(self.target_url, echo=False)
        self.source_sessionmaker = async_sessionmaker(self.source_engine, expire_on_commit=False)
        self.target_sessionmaker = async_sessionmaker(self.target_engine, expire_on_commit=False)

    async def close_connections(self):
        """Close database connections."""
        logger.info("Closing database connections")
        if self.source_engine:
            await self.source_engine.dispose()
        if self.target_engine:
            await self.target_engine.dispose()

    async def transfer_users(self) -> tuple[int, int]:
        """
        Transfer User data from source to target.
        Returns tuple of (processed_count, inserted_count).
        """
        logger.info("Starting User transfer")

        # Query source data - fetch all user fields
        async with self.source_sessionmaker() as source_session:
            query = text("""
                SELECT id, email, hashed_password, is_active, is_superuser, is_verified,
                       first_name, last_name, api_key
                FROM "user"
                ORDER BY id
            """)
            result = await source_session.execute(query)
            source_rows = result.fetchall()

        logger.info("Fetched source users", count=len(source_rows))

        if not source_rows:
            logger.info("No users to transfer")
            return 0, 0

        if self.dry_run:
            logger.info("DRY RUN: Would insert users", count=len(source_rows))
            # Build mapping for dry-run (use source IDs as target IDs for preview)
            for row in source_rows:
                self.user_id_map[row.id] = row.id
            return len(source_rows), 0

        # Insert users into target with ON CONFLICT UPDATE
        inserted_count = 0
        async with self.target_sessionmaker() as target_session:
            for row in source_rows:
                # Insert or update user
                insert_query = text("""
                    INSERT INTO "user" (email, hashed_password, is_active, is_superuser, is_verified,
                                        first_name, last_name, api_key)
                    VALUES (:email, :hashed_password, :is_active, :is_superuser, :is_verified,
                            :first_name, :last_name, :api_key)
                    ON CONFLICT (email) DO UPDATE SET
                        hashed_password = EXCLUDED.hashed_password,
                        is_active = EXCLUDED.is_active,
                        is_superuser = EXCLUDED.is_superuser,
                        is_verified = EXCLUDED.is_verified,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        api_key = EXCLUDED.api_key
                    RETURNING id
                """)

                result = await target_session.execute(
                    insert_query,
                    {
                        "email": row.email,
                        "hashed_password": row.hashed_password,
                        "is_active": row.is_active,
                        "is_superuser": row.is_superuser,
                        "is_verified": row.is_verified,
                        "first_name": row.first_name,
                        "last_name": row.last_name,
                        "api_key": row.api_key,
                    },
                )
                target_id = result.scalar()
                self.user_id_map[row.id] = target_id

                # Check if this was insert or update (simple heuristic)
                if target_id:
                    inserted_count += 1
                    logger.debug(
                        "User transferred",
                        email=row.email,
                        source_id=row.id,
                        target_id=target_id,
                    )

            await target_session.commit()

        logger.info(
            "User transfer complete",
            processed=len(source_rows),
            inserted_or_updated=inserted_count,
        )
        return len(source_rows), inserted_count

    async def transfer_inverters(self) -> tuple[int, int]:
        """
        Transfer Inverter data from source to target.
        Returns tuple of (processed_count, inserted_count).
        """
        logger.info("Starting Inverter transfer")

        # Query source data
        async with self.source_sessionmaker() as source_session:
            query = text("""
                SELECT id, user_id, name, serial_logger, sw_version, rated_power, number_of_mppts
                FROM inverter
                ORDER BY id
            """)
            result = await source_session.execute(query)
            source_rows = result.fetchall()

        logger.info("Fetched source inverters", count=len(source_rows))

        if not source_rows:
            logger.info("No inverters to transfer")
            return 0, 0

        # Check user mappings
        missing_users = []
        for row in source_rows:
            if row.user_id not in self.user_id_map:
                missing_users.append(row.user_id)

        if missing_users:
            logger.error(
                "Cannot transfer inverters: some users not mapped",
                missing_user_ids=list(set(missing_users)),
            )
            return 0, 0

        if self.dry_run:
            logger.info("DRY RUN: Would insert inverters", count=len(source_rows))
            # Build mapping for dry-run
            for row in source_rows:
                self.inverter_id_map[row.id] = row.id
            return len(source_rows), 0

        # Insert inverters into target with ON CONFLICT UPDATE
        inserted_count = 0
        async with self.target_sessionmaker() as target_session:
            for row in source_rows:
                target_user_id = self.user_id_map[row.user_id]

                # Insert or update inverter
                insert_query = text("""
                    INSERT INTO inverter (user_id, name, serial_logger, sw_version, rated_power, number_of_mppts)
                    VALUES (:user_id, :name, :serial_logger, :sw_version, :rated_power, :number_of_mppts)
                    ON CONFLICT (serial_logger) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        name = EXCLUDED.name,
                        sw_version = EXCLUDED.sw_version,
                        rated_power = EXCLUDED.rated_power,
                        number_of_mppts = EXCLUDED.number_of_mppts
                    RETURNING id
                """)

                result = await target_session.execute(
                    insert_query,
                    {
                        "user_id": target_user_id,
                        "name": row.name,
                        "serial_logger": row.serial_logger,
                        "sw_version": row.sw_version,
                        "rated_power": row.rated_power,
                        "number_of_mppts": row.number_of_mppts,
                    },
                )
                target_id = result.scalar()
                self.inverter_id_map[row.id] = target_id

                if target_id:
                    inserted_count += 1
                    logger.debug(
                        "Inverter transferred",
                        serial=row.serial_logger,
                        source_id=row.id,
                        target_id=target_id,
                    )

            await target_session.commit()

        logger.info(
            "Inverter transfer complete",
            processed=len(source_rows),
            inserted_or_updated=inserted_count,
        )
        return len(source_rows), inserted_count

    async def build_user_mapping(self):
        """Build user ID mapping between source and target databases by email."""
        logger.info("Building user ID mapping")

        async with self.source_sessionmaker() as source_session:
            result = await source_session.execute(text('SELECT id, email FROM "user" ORDER BY id'))
            source_users = {email: user_id for user_id, email in result.fetchall()}

        async with self.target_sessionmaker() as target_session:
            result = await target_session.execute(text('SELECT id, email FROM "user" ORDER BY id'))
            target_users = {email: user_id for user_id, email in result.fetchall()}

        # Build mapping
        missing_users = []
        for email, source_id in source_users.items():
            if email in target_users:
                self.user_id_map[source_id] = target_users[email]
                logger.debug(
                    "User mapped",
                    email=email,
                    source_id=source_id,
                    target_id=target_users[email],
                )
            else:
                missing_users.append(email)

        if missing_users:
            logger.error(
                "Users exist in source but not in target",
                count=len(missing_users),
                emails=missing_users,
            )
            return False

        logger.info(
            "User mapping complete",
            mapped_count=len(self.user_id_map),
            source_count=len(source_users),
            target_count=len(target_users),
        )
        return True

    async def build_inverter_mapping(self):
        """Build inverter ID mapping between source and target databases by serial_logger."""
        logger.info("Building inverter ID mapping")

        async with self.source_sessionmaker() as source_session:
            result = await source_session.execute(text("SELECT id, serial_logger, user_id FROM inverter ORDER BY id"))
            source_inverters = {serial: (inv_id, user_id) for inv_id, serial, user_id in result.fetchall()}

        async with self.target_sessionmaker() as target_session:
            result = await target_session.execute(text("SELECT id, serial_logger, user_id FROM inverter ORDER BY id"))
            target_inverters = {serial: (inv_id, user_id) for inv_id, serial, user_id in result.fetchall()}

        # Build mapping
        missing_inverters = []
        for serial, (source_id, source_user_id) in source_inverters.items():
            if serial in target_inverters:
                target_id, target_user_id = target_inverters[serial]

                # Check if user mapping is consistent
                expected_target_user_id = self.user_id_map.get(source_user_id)
                if expected_target_user_id != target_user_id:
                    logger.warning(
                        "Inverter user mismatch",
                        serial=serial,
                        source_user_id=source_user_id,
                        target_user_id=target_user_id,
                        expected_target_user_id=expected_target_user_id,
                    )

                self.inverter_id_map[source_id] = target_id
                logger.debug(
                    "Inverter mapped",
                    serial=serial,
                    source_id=source_id,
                    target_id=target_id,
                )
            else:
                missing_inverters.append(serial)

        if missing_inverters:
            logger.error(
                "Inverters exist in source but not in target",
                count=len(missing_inverters),
                serials=missing_inverters,
            )
            return False

        logger.info(
            "Inverter mapping complete",
            mapped_count=len(self.inverter_id_map),
            source_count=len(source_inverters),
            target_count=len(target_inverters),
        )
        return True

    async def transfer_inverter_measurements(self) -> tuple[int, int]:
        """
        Transfer InverterMeasurement data.
        Returns tuple of (processed_count, inserted_count).
        """
        logger.info(
            "Starting InverterMeasurement transfer",
            start_date=self.start_date.isoformat(),
            end_date=self.end_date.isoformat(),
        )

        # Query source data
        # Calculate end datetime (end_date + 1 day) to include all of end_date
        end_datetime = self.end_date + timedelta(days=1)

        async with self.source_sessionmaker() as source_session:
            query = text("""
                SELECT time, user_id, inverter_id, total_output_power, yield_day_wh, yield_total_kwh
                FROM inverter_measurements
                WHERE time >= :start_date AND time < :end_datetime
                ORDER BY time, user_id, inverter_id
            """)
            result = await source_session.execute(
                query,
                {"start_date": self.start_date, "end_datetime": end_datetime},
            )
            source_rows = result.fetchall()

        logger.info("Fetched source measurements", count=len(source_rows))

        if not source_rows:
            logger.info("No measurements to transfer")
            return 0, 0

        # Map IDs and prepare target rows
        target_rows = []
        skipped_count = 0
        for row in source_rows:
            source_user_id = row.user_id
            source_inverter_id = row.inverter_id

            # Check if we have mappings
            if source_user_id not in self.user_id_map:
                skipped_count += 1
                continue
            if source_inverter_id not in self.inverter_id_map:
                skipped_count += 1
                continue

            target_rows.append(
                {
                    "time": row.time,
                    "user_id": self.user_id_map[source_user_id],
                    "inverter_id": self.inverter_id_map[source_inverter_id],
                    "total_output_power": row.total_output_power,
                    "yield_day_wh": row.yield_day_wh,
                    "yield_total_kwh": row.yield_total_kwh,
                }
            )

        if skipped_count > 0:
            logger.warning("Skipped measurements due to missing mappings", count=skipped_count)

        logger.info("Prepared target measurements", count=len(target_rows))

        if self.dry_run:
            logger.info("DRY RUN: Would insert measurements", count=len(target_rows))
            return len(source_rows), 0

        # Insert into target in batches
        inserted_count = 0
        async with self.target_sessionmaker() as target_session:
            for i in range(0, len(target_rows), self.batch_size):
                batch = target_rows[i : i + self.batch_size]

                insert_query = text("""
                    INSERT INTO inverter_measurements
                    (time, user_id, inverter_id, total_output_power, yield_day_wh, yield_total_kwh)
                    VALUES (:time, :user_id, :inverter_id, :total_output_power, :yield_day_wh, :yield_total_kwh)
                """)

                result = await target_session.execute(insert_query, batch)
                batch_inserted = result.rowcount
                inserted_count += batch_inserted

                logger.info(
                    "Inserted batch",
                    batch_num=i // self.batch_size + 1,
                    batch_size=len(batch),
                    inserted=batch_inserted,
                )

            await target_session.commit()

        logger.info(
            "InverterMeasurement transfer complete",
            processed=len(source_rows),
            prepared=len(target_rows),
            inserted=inserted_count,
            skipped=len(source_rows) - inserted_count,
        )
        return len(source_rows), inserted_count

    async def transfer_dc_channel_measurements(self) -> tuple[int, int]:
        """
        Transfer DCChannelMeasurement data.
        Returns tuple of (processed_count, inserted_count).
        """
        logger.info(
            "Starting DCChannelMeasurement transfer",
            start_date=self.start_date.isoformat(),
            end_date=self.end_date.isoformat(),
        )

        # Query source data
        # Calculate end datetime (end_date + 1 day) to include all of end_date
        end_datetime = self.end_date + timedelta(days=1)

        async with self.source_sessionmaker() as source_session:
            query = text("""
                SELECT time, user_id, inverter_id, channel, name,
                       power, voltage, current, yield_day_wh, yield_total_kwh, irradiation
                FROM dc_channel_measurements
                WHERE time >= :start_date AND time < :end_datetime
                ORDER BY time, user_id, inverter_id, channel
            """)
            result = await source_session.execute(
                query,
                {"start_date": self.start_date, "end_datetime": end_datetime},
            )
            source_rows = result.fetchall()

        logger.info("Fetched source DC channel measurements", count=len(source_rows))

        if not source_rows:
            logger.info("No DC channel measurements to transfer")
            return 0, 0

        # Map IDs and prepare target rows
        target_rows = []
        skipped_count = 0
        for row in source_rows:
            source_user_id = row.user_id
            source_inverter_id = row.inverter_id

            # Check if we have mappings
            if source_user_id not in self.user_id_map:
                skipped_count += 1
                continue
            if source_inverter_id not in self.inverter_id_map:
                skipped_count += 1
                continue

            target_rows.append(
                {
                    "time": row.time,
                    "user_id": self.user_id_map[source_user_id],
                    "inverter_id": self.inverter_id_map[source_inverter_id],
                    "channel": row.channel,
                    "name": row.name,
                    "power": row.power,
                    "voltage": row.voltage,
                    "current": row.current,
                    "yield_day_wh": row.yield_day_wh,
                    "yield_total_kwh": row.yield_total_kwh,
                    "irradiation": row.irradiation,
                }
            )

        if skipped_count > 0:
            logger.warning("Skipped DC channel measurements due to missing mappings", count=skipped_count)

        logger.info("Prepared target DC channel measurements", count=len(target_rows))

        if self.dry_run:
            logger.info("DRY RUN: Would insert DC channel measurements", count=len(target_rows))
            return len(source_rows), 0

        # Insert into target in batches
        inserted_count = 0
        async with self.target_sessionmaker() as target_session:
            for i in range(0, len(target_rows), self.batch_size):
                batch = target_rows[i : i + self.batch_size]

                insert_query = text("""
                    INSERT INTO dc_channel_measurements
                    (time, user_id, inverter_id, channel, name,
                     power, voltage, current, yield_day_wh, yield_total_kwh, irradiation)
                    VALUES (:time, :user_id, :inverter_id, :channel, :name,
                            :power, :voltage, :current, :yield_day_wh, :yield_total_kwh, :irradiation)
                    ON CONFLICT (time, user_id, inverter_id, channel) DO NOTHING
                """)

                result = await target_session.execute(insert_query, batch)
                batch_inserted = result.rowcount
                inserted_count += batch_inserted

                logger.info(
                    "Inserted DC channel batch",
                    batch_num=i // self.batch_size + 1,
                    batch_size=len(batch),
                    inserted=batch_inserted,
                )

            await target_session.commit()

        logger.info(
            "DCChannelMeasurement transfer complete",
            processed=len(source_rows),
            prepared=len(target_rows),
            inserted=inserted_count,
            skipped=len(source_rows) - inserted_count,
        )
        return len(source_rows), inserted_count

    async def run(self) -> bool:
        """Execute the full transfer process."""
        try:
            await self.init_connections()

            # Step 1: Transfer users if requested
            users_processed = 0
            users_inserted = 0
            if self.should_transfer_users:
                users_processed, users_inserted = await self.transfer_users()
            else:
                # Build user mapping from existing data
                if not await self.build_user_mapping():
                    logger.error("Failed to build user mapping. Aborting.")
                    return False

            # Step 2: Transfer inverters if requested (depends on users)
            inverters_processed = 0
            inverters_inserted = 0
            if self.should_transfer_inverters:
                inverters_processed, inverters_inserted = await self.transfer_inverters()
            else:
                # Build inverter mapping from existing data
                if not await self.build_inverter_mapping():
                    logger.error("Failed to build inverter mapping. Aborting.")
                    return False

            # Step 3: Transfer measurements (depends on users and inverters)
            inv_processed, inv_inserted = await self.transfer_inverter_measurements()
            dc_processed, dc_inserted = await self.transfer_dc_channel_measurements()

            # Summary
            summary_data = {
                "inverter_measurements_processed": inv_processed,
                "inverter_measurements_inserted": inv_inserted,
                "dc_channel_measurements_processed": dc_processed,
                "dc_channel_measurements_inserted": dc_inserted,
                "dry_run": self.dry_run,
            }

            if self.should_transfer_users:
                summary_data["users_processed"] = users_processed
                summary_data["users_inserted"] = users_inserted

            if self.should_transfer_inverters:
                summary_data["inverters_processed"] = inverters_processed
                summary_data["inverters_inserted"] = inverters_inserted

            logger.info("Transfer complete", **summary_data)

            return True

        except Exception as e:
            logger.exception("Transfer failed", error=str(e))
            return False
        finally:
            await self.close_connections()


def parse_date(date_string: str) -> date:
    """Parse ISO date string (YYYY-MM-DD)."""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD") from e


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Transfer measurements between TimescaleDB instances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transfer only measurements (requires users/inverters to exist in target)
  %(prog)s \\
    --source-url "postgresql+asyncpg://user:pass@source:5432/db" \\
    --target-url "postgresql+asyncpg://user:pass@target:5432/db" \\
    --start-date "2025-10-31" \\
    --end-date "2025-10-31"

  # Transfer users, inverters, and measurements (dry run)
  %(prog)s \\
    --source-url "$SOURCE_DB_URL" \\
    --target-url "$TARGET_DB_URL" \\
    --start-date "2025-10-01" \\
    --end-date "2025-10-31" \\
    --users --inverters \\
    --dry-run

  # Transfer only users and inverters (no measurements)
  %(prog)s \\
    --source-url "$SOURCE_DB_URL" \\
    --target-url "$TARGET_DB_URL" \\
    --start-date "2025-10-31" \\
    --end-date "2025-10-31" \\
    --users --inverters
        """,
    )

    parser.add_argument(
        "--source-url",
        required=True,
        help="Source database URL (postgresql+asyncpg://...)",
    )
    parser.add_argument(
        "--target-url",
        required=True,
        help="Target database URL (postgresql+asyncpg://...)",
    )
    parser.add_argument(
        "--start-date",
        type=parse_date,
        required=True,
        help="Start date (YYYY-MM-DD, inclusive)",
    )
    parser.add_argument(
        "--end-date",
        type=parse_date,
        required=True,
        help="End date (YYYY-MM-DD, inclusive)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for inserts (default: 1000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview transfer without making changes",
    )
    parser.add_argument(
        "--users",
        action="store_true",
        help="Transfer users from source to target (with upsert on email conflict)",
    )
    parser.add_argument(
        "--inverters",
        action="store_true",
        help="Transfer inverters from source to target (with upsert on serial_logger conflict)",
    )

    args = parser.parse_args()

    # Validate date range
    if args.start_date > args.end_date:
        logger.error("Start date must be before or equal to end date")
        sys.exit(1)

    # Create and run transfer
    transfer = MeasurementTransfer(
        source_url=args.source_url,
        target_url=args.target_url,
        start_date=args.start_date,
        end_date=args.end_date,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        transfer_users=args.users,
        transfer_inverters=args.inverters,
    )

    success = asyncio.run(transfer.run())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
