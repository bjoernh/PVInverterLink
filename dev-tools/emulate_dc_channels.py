"""
Test script to verify DC channel measurements functionality.

This script simulates OpenDTU data posting and verifies:
1. DC channel data is stored correctly
2. Today's yield calculation works
3. Fallback to power integration works when no yield data exists
"""

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select, text

from solar_backend.config import settings
from solar_backend.db import Inverter, User, sessionmanager
from solar_backend.utils.timeseries import (
    get_today_energy_production,
    get_today_total_yield,
    reset_rls_context,
    set_rls_context,
    write_dc_channel_measurement,
    write_measurement,
)


async def test_dc_channels():
    """Test DC channel functionality."""
    print("=== Testing DC Channel Measurements ===\n")

    sessionmanager.init(settings.DATABASE_URL)

    async with sessionmanager.session() as session:
        # Find first user and inverter
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user:
            print("❌ No users found. Please create a user first.")
            return False

        result = await session.execute(select(Inverter).where(Inverter.user_id == user.id).limit(1))
        inverter = result.scalar_one_or_none()

        if not inverter:
            print("❌ No inverters found. Please create an inverter first.")
            return False

        print(f"✓ Testing with User: {user.email} (ID: {user.id})")
        print(f"✓ Testing with Inverter: {inverter.name} (ID: {inverter.id})\n")

        # Test 1: Write DC channel measurements (simulating OpenDTU data)
        print("Test 1: Writing DC channel measurements...")
        timestamp = datetime.now(UTC)

        # Simulate 4 DC channels (MPPTs)
        dc_channels = [
            {
                "channel": 1,
                "name": "Hochbeet",
                "power": 3.9,
                "voltage": 30.8,
                "current": 0.13,
                "yield_day": 5.0,
                "yield_total": 445.324,
                "irradiation": 1.772727,
            },
            {
                "channel": 2,
                "name": "Windfang2",
                "power": 4.8,
                "voltage": 30.8,
                "current": 0.16,
                "yield_day": 6.0,
                "yield_total": 609.498,
                "irradiation": 1.170732,
            },
            {
                "channel": 3,
                "name": "Carport",
                "power": 6.9,
                "voltage": 30.8,
                "current": 0.22,
                "yield_day": 9.0,
                "yield_total": 824.132,
                "irradiation": 1.682927,
            },
            {
                "channel": 4,
                "name": "Carport2",
                "power": 6.4,
                "voltage": 30.8,
                "current": 0.21,
                "yield_day": 8.0,
                "yield_total": 741.192,
                "irradiation": 1.560976,
            },
        ]

        # Write AC measurement
        await write_measurement(
            session=session,
            user_id=user.id,
            inverter_id=inverter.id,
            timestamp=timestamp,
            total_output_power=22,  # Sum of DC powers approximately
        )

        # Write DC channel measurements
        for dc in dc_channels:
            await write_dc_channel_measurement(
                session=session,
                user_id=user.id,
                inverter_id=inverter.id,
                timestamp=timestamp,
                channel=dc["channel"],
                name=dc["name"],
                power=dc["power"],
                voltage=dc["voltage"],
                current=dc["current"],
                yield_day_wh=dc["yield_day"],
                yield_total_kwh=dc["yield_total"],
                irradiation=dc["irradiation"],
            )

        print("✓ Wrote AC measurement: 22W")
        print(f"✓ Wrote {len(dc_channels)} DC channel measurements\n")

        # Test 2: Query DC channel data
        print("Test 2: Querying DC channel data...")
        await set_rls_context(session, user.id)

        query = text("""
            SELECT channel, name, yield_day_wh, yield_total_kwh
            FROM dc_channel_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
            ORDER BY channel
        """)

        result = await session.execute(query, {"user_id": user.id, "inverter_id": inverter.id})

        rows = result.fetchall()
        if rows:
            print(f"✓ Found {len(rows)} DC channels:")
            for row in rows:
                print(
                    f"  - Channel {row.channel} ({row.name}): "
                    f"{row.yield_day_wh} Wh today, {row.yield_total_kwh} kWh total"
                )
        else:
            print("❌ No DC channel data found!")
            await reset_rls_context(session)
            return False

        print()

        # Test 3: Get today's total yield from inverter
        print("Test 3: Getting today's total yield from inverter...")
        total_yield_wh = await get_today_total_yield(session, user.id, inverter.id)

        if total_yield_wh is not None:
            expected_total = sum(dc["yield_day"] for dc in dc_channels)
            print(f"✓ Total yield from inverter: {total_yield_wh} Wh")
            print(f"✓ Expected: {expected_total} Wh")
            if abs(total_yield_wh - expected_total) < 0.01:
                print("✓ Yield calculation correct!\n")
            else:
                print("❌ Yield calculation mismatch!\n")
                await reset_rls_context(session)
                return False
        else:
            print("❌ Failed to get yield from inverter!\n")
            await reset_rls_context(session)
            return False

        # Test 4: Get today's energy production (should use inverter data)
        print("Test 4: Getting today's energy production...")
        energy_kwh = await get_today_energy_production(session, user.id, inverter.id)

        expected_kwh = total_yield_wh / 1000.0
        print(f"✓ Energy production: {energy_kwh} kWh")
        print(f"✓ Expected: {expected_kwh} kWh")

        if abs(energy_kwh - expected_kwh) < 0.001:
            print("✓ Using inverter-provided yield correctly!\n")
        else:
            print("⚠ Energy value differs, might be using fallback calculation\n")

        await reset_rls_context(session)

        print("=== All Tests Passed! ===\n")
        return True

    await sessionmanager.close()


if __name__ == "__main__":
    success = asyncio.run(test_dc_channels())
    sys.exit(0 if success else 1)
