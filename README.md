# Backup

## Manifest structure

```json
{
  "archive_name": "my_cool_backup.tar.gz",
  "checksum": "517cf1c6c4c9b3b8208c5dd85975243190f9c63fd5a35682c8fc542071468993",
  "checksum_algorithm": "sha3_256",
  "creation_time": 1568988985,
  "files": [
    {
      "path": "foo/bar.txt",
      "checksum": "a0e570324e6ffdbc6b9c813dec968d9bad134bc0dbb061530934f4e59c2700b9",
    },
    ...
  ]
}
```
