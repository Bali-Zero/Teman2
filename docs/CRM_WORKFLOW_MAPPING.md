# CRM to Workflow Mapping

This document defines the logic for personalizing workflows based on CRM data and user memory.

## CRM Field Mapping

| CRM Field | Workflow Step | Filter/Skip Logic |
| :--- | :--- | :--- |
| `clients.has_npwp` (custom_field) | NPWP Tax Registration | Skip if `true` |
| `clients.passport_number` | Submit Passport Copy | Mark as completed if present |
| `clients.passport_expiry` | Passport Renewal | Add as high-priority step if `< 6 months` |
| `clients.date_of_birth` | Retirement Eligibility | Only show "Retirement KITAS" if `age >= 55` |
| `practices.status == 'completed'` | Full Workflow | Skip entire workflow if already completed |
| `practices.payment_status == 'paid'` | Deposit Payment | Skip payment step |
| `practices.missing_documents` | Document Submission | Only show steps for documents in this list |

## Memory-Enhanced Logic

| Memory Fact Type | Workflow Step | Personalization |
| :--- | :--- | :--- |
| `preference:visa_type` | Visa Selection | Pre-select preferred visa in the workflow |
| `fact:already_has_pma` | Company Setup | Show "Expansion" workflow instead of "New Incorporation" |
| `fact:urgency` | All Steps | Compress timelines and flag steps as `URGENT` |

## Filter Logic Example

```python
# Pseudo-code for personalization engine
def filter_workflow(base_workflow, user_data, completed_steps):
    filtered_steps = []
    for step in base_workflow['steps']:
        # Skip logic
        if step['id'] == 'npwp_registration' and user_data.get('has_npwp'):
            continue
        
        if step['id'] in completed_steps:
            step['status'] = 'completed'
            
        # Urgency logic
        if user_data.get('urgency') == 'high':
            step['priority'] = 'urgent'
            
        filtered_steps.append(step)
    
    return filtered_steps
```
