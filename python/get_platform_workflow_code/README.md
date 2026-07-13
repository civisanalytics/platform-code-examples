# get_platform_workflow_code

Downloads all scripts from a Civis Platform workflow into a local folder, preserving the workflow's structure. Useful when you want to audit, version-control, or share the code behind a workflow without clicking through Platform one script at a time.

Sub-workflows are handled automatically — they become subdirectories, and their scripts are downloaded recursively.

## Output structure

```
workflow_4742_scripts/
    step_01_my_subworkflow/      ← sub-workflow → folder
        step_01_clean_data.sql
        step_02_model.py
    step_02_export_results.sql   ← direct script → file
    step_03_notify.py
```

Each file gets a small header comment with the workflow ID, execution ID, and job ID for traceability.

## Setup

```bash
pip install civis
export CIVIS_API_KEY="your_api_key"
```

## Usage

1. Open [get_platform_workflow_code.py](get_platform_workflow_code.py) and set `WORKFLOW_ID` to the ID of the workflow you want to download.
2. Run the script:

```bash
python get_platform_workflow_code.py
```

The scripts will be saved to `workflow_<id>_scripts/` in your current directory.

## Notes

- The script downloads code from the **most recent execution** of the workflow.
- Supported script types: Python, SQL, R, JavaScript, and container scripts.
- Tasks that were skipped during the last execution will produce a placeholder `.txt` file.
