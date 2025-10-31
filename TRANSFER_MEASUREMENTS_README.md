# Measurement Transfer Script

## Overview

`transfer_measurements.py` is a CLI tool for transferring data between TimescaleDB instances for testing purposes. It can transfer:

- **Users** (with `--users` flag)
- **Inverters** (with `--inverters` flag)
- **Measurements** (InverterMeasurement and DCChannelMeasurement - always transferred)

## Prerequisites

**Without `--users` and `--inverters` flags:**
- Users and inverters must already exist in the target database
- Users are matched by `email`
- Inverters are matched by `serial_logger`

**With `--users` and/or `--inverters` flags:**
- Users and/or inverters will be created or updated in the target database
- Conflicts are handled via upsert (ON CONFLICT DO UPDATE)

**General:**
- Both databases must have the same schema version

## Features

- **Selective date range**: Transfer only specific date ranges
- **Skip duplicates**: Uses `ON CONFLICT DO NOTHING` to avoid overwriting existing data
- **ID mapping**: Automatically maps user_id and inverter_id between databases
- **Batch processing**: Efficient bulk inserts with configurable batch size
- **Dry-run mode**: Preview transfers without making changes
- **Progress logging**: Detailed logging with structured output

## Usage

### Basic Usage

```bash
uv run python transfer_measurements.py \
  --source-url "postgresql+asyncpg://user:pass@source-host:5432/dbname" \
  --target-url "postgresql+asyncpg://user:pass@target-host:5432/dbname" \
  --start-date "2025-10-31" \
  --end-date "2025-10-31"
```

### Using Environment Variables

```bash
# Set connection strings in environment
export SOURCE_DB_URL="postgresql+asyncpg://deyehard:password@prod-server:5432/deyehard"
export TARGET_DB_URL="postgresql+asyncpg://deyehard:dev-testing-ok@localhost:5432/deyehard"

# Transfer last 7 days
uv run python transfer_measurements.py \
  --source-url "$SOURCE_DB_URL" \
  --target-url "$TARGET_DB_URL" \
  --start-date "2025-10-24" \
  --end-date "2025-10-31"
```

### Dry Run (Preview)

```bash
uv run python transfer_measurements.py \
  --source-url "$SOURCE_DB_URL" \
  --target-url "$TARGET_DB_URL" \
  --start-date "2025-10-31" \
  --end-date "2025-10-31" \
  --dry-run
```

### Custom Batch Size

```bash
# Use larger batches for faster transfers (requires more memory)
uv run python transfer_measurements.py \
  --source-url "$SOURCE_DB_URL" \
  --target-url "$TARGET_DB_URL" \
  --start-date "2025-10-01" \
  --end-date "2025-10-31" \
  --batch-size 5000
```

## Command-Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--source-url` | Yes | Source database connection URL (postgresql+asyncpg://...) |
| `--target-url` | Yes | Target database connection URL (postgresql+asyncpg://...) |
| `--start-date` | Yes | Start date (YYYY-MM-DD, inclusive) |
| `--end-date` | Yes | End date (YYYY-MM-DD, inclusive) |
| `--batch-size` | No | Number of records per batch insert (default: 1000) |
| `--dry-run` | No | Preview transfer without making changes |
| `--users` | No | Transfer users from source to target (upsert on email conflict) |
| `--inverters` | No | Transfer inverters from source to target (upsert on serial_logger conflict) |

## Examples

### Transfer Today's Measurements Only (Users/Inverters Must Exist)

```bash
uv run python transfer_measurements.py \
  --source-url "postgresql+asyncpg://user:pass@prod:5432/deyehard" \
  --target-url "postgresql+asyncpg://deyehard:dev-testing-ok@localhost:5432/deyehard" \
  --start-date "2025-10-31" \
  --end-date "2025-10-31"
```

### Transfer Users, Inverters, and Measurements

```bash
uv run python transfer_measurements.py \
  --source-url "$PROD_DB_URL" \
  --target-url "$TEST_DB_URL" \
  --start-date "2025-10-31" \
  --end-date "2025-10-31" \
  --users --inverters
```

### Transfer Multiple Days with All Data

```bash
uv run python transfer_measurements.py \
  --source-url "$PROD_DB_URL" \
  --target-url "$TEST_DB_URL" \
  --start-date "2025-10-01" \
  --end-date "2025-10-07" \
  --users --inverters
```

### Transfer Only Users and Inverters (No Measurements)

Since measurements are always transferred, you still need to specify dates, but measurements will only be transferred if they exist in that date range:

```bash
uv run python transfer_measurements.py \
  --source-url "$PROD_DB_URL" \
  --target-url "$TEST_DB_URL" \
  --start-date "2025-10-31" \
  --end-date "2025-10-31" \
  --users --inverters
```

### Check What Would Be Transferred (Dry Run)

```bash
uv run python transfer_measurements.py \
  --source-url "$PROD_DB_URL" \
  --target-url "$TEST_DB_URL" \
  --start-date "2025-10-31" \
  --end-date "2025-10-31" \
  --users --inverters \
  --dry-run
```

## Output

The script provides structured logging with the following information:

**Example output with --users and --inverters:**

```
[info     ] Initializing database connections
[info     ] Starting User transfer
[info     ] Fetched source users          count=5
[info     ] User transfer complete        inserted_or_updated=5 processed=5
[info     ] Starting Inverter transfer
[info     ] Fetched source inverters      count=12
[info     ] Inverter transfer complete    inserted_or_updated=12 processed=12
[info     ] Starting InverterMeasurement transfer start_date=2025-10-31 end_date=2025-10-31
[info     ] Fetched source measurements   count=1440
[info     ] Prepared target measurements  count=1440
[info     ] Inserted batch                batch_num=1 batch_size=1000 inserted=980
[info     ] Inserted batch                batch_num=2 batch_size=440 inserted=420
[info     ] InverterMeasurement transfer complete inserted=1400 prepared=1440 processed=1440 skipped=40
[info     ] Starting DCChannelMeasurement transfer start_date=2025-10-31 end_date=2025-10-31
[info     ] Fetched source DC channel measurements count=5760
[info     ] Prepared target DC channel measurements count=5760
[info     ] Inserted DC channel batch     batch_num=1 batch_size=1000 inserted=950
...
[info     ] DCChannelMeasurement transfer complete inserted=5500 prepared=5760 processed=5760 skipped=260
[info     ] Transfer complete             dc_channel_measurements_inserted=5500 dc_channel_measurements_processed=5760 inverter_measurements_inserted=1400 inverter_measurements_processed=1440 inverters_inserted=12 inverters_processed=12 users_inserted=5 users_processed=5
```

**Example output without --users and --inverters (mapping existing data):**

```
[info     ] Initializing database connections
[info     ] Building user ID mapping
[info     ] User mapping complete         mapped_count=5 source_count=5 target_count=5
[info     ] Building inverter ID mapping
[info     ] Inverter mapping complete     mapped_count=12 source_count=12 target_count=12
[info     ] Starting InverterMeasurement transfer start_date=2025-10-31 end_date=2025-10-31
[info     ] Fetched source measurements   count=1440
...
[info     ] Transfer complete             dc_channel_measurements_inserted=5500 dc_channel_measurements_processed=5760 inverter_measurements_inserted=1400 inverter_measurements_processed=1440
```

## Error Handling

### Missing Users or Inverters

If users or inverters exist in the source but not in the target, the script will report them and abort:

```
[error    ] Users exist in source but not in target count=2 emails=['user@example.com', 'other@example.com']
[error    ] Failed to build user mapping. Aborting.
```

**Solution**: Ensure all users and inverters exist in the target database before running the transfer.

### User/Inverter Ownership Mismatch

If an inverter belongs to different users in source vs target:

```
[warning  ] Inverter user mismatch        serial=ABC123 source_user_id=5 target_user_id=8
```

**Note**: The script will still proceed but measurements will be associated with the target database's user_id.

### Connection Errors

If database connections fail:

```
[error    ] Transfer failed               error='could not connect to server'
```

**Solution**: Verify database URLs and network connectivity.

## Important Notes

1. **Date Range is Inclusive**: Both start and end dates are included in the transfer
2. **Duplicate Handling**:
   - Users: Upserted on `email` conflict (existing user updated)
   - Inverters: Upserted on `serial_logger` conflict (existing inverter updated)
   - Measurements: Skipped on composite primary key conflict (no updates)
3. **Transfer Order**: Users → Inverters → Measurements (dependencies respected)
4. **No RLS Context**: Script runs with superuser privileges and doesn't use Row-Level Security
5. **Time Zone Handling**: All timestamps are treated as-is from the source database
6. **No Data Transformation**: Data is copied exactly as-is (no unit conversion or validation)
7. **Password Hashing**: User passwords (hashed) are copied as-is - users can still log in with their original passwords

## Security Considerations

- **Database Credentials**: Never commit database URLs with credentials to version control
- **Use Environment Variables**: Store connection strings in environment variables or config files
- **Read-Only Source**: The script only reads from source (never modifies it)
- **Transaction Safety**: Target inserts are committed in batches; partial failures will result in partial data

## Performance Tips

1. **Batch Size**: Increase `--batch-size` for faster transfers (1000-5000 works well)
2. **Network Latency**: Run from a location close to both databases
3. **Date Ranges**: Transfer smaller date ranges for more frequent testing
4. **Indexes**: Ensure composite primary key indexes exist on both databases

## Troubleshooting

### Script Hangs or Times Out

- Reduce batch size
- Check network connectivity
- Verify database server resources

### Memory Issues

- Reduce batch size
- Transfer smaller date ranges
- Monitor Python process memory usage

### Incorrect Row Counts

- Verify user/inverter mappings are correct
- Check for missing foreign key relationships
- Use `--dry-run` to preview transfers

## Future Enhancements

Possible improvements for future versions:

- Support for user/inverter filtering (transfer subset of data)
- Parallel batch processing for faster transfers
- Progress bar for long-running transfers
- Resume capability for interrupted transfers
- Data validation and sanity checks
- Support for other measurement tables if added in future
