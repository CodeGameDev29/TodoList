export class HttpError extends Error {
  constructor(status, message, fields) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

export function validateListQuery(parameters) {
  const choices = {
    status: ['all', 'incomplete', 'completed', 'overdue'],
    sortBy: ['createdAt', 'dueDate', 'title'],
    order: ['asc', 'desc'],
  };
  const fields = Object.create(null);
  const output = { status: 'all', sortBy: 'createdAt', order: 'desc' };
  const seen = new Set();
  for (const [key, value] of parameters) {
    if (!Object.hasOwn(choices, key)) fields[key] = 'Unknown query parameter.';
    else if (seen.has(key)) fields[key] = 'Provide this query parameter only once.';
    else if (!choices[key].includes(value)) fields[key] = `Must be one of: ${choices[key].join(', ')}.`;
    else output[key] = value;
    seen.add(key);
  }
  if (Object.keys(fields).length) throw new HttpError(400, 'Please correct the invalid query parameters.', fields);
  return output;
}

function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

export function validateTask(body, partial = false) {
  if (body === null || typeof body !== 'object' || Array.isArray(body)) {
    throw new HttpError(400, 'Request body must be a JSON object.');
  }
  const allowed = ['title', 'description', 'dueDate', ...(partial ? ['isCompleted'] : [])];
  const fields = Object.create(null);
  for (const key of Object.keys(body)) {
    if (!allowed.includes(key)) fields[key] = 'Unknown field.';
  }
  if (partial && Object.keys(body).length === 0) throw new HttpError(400, 'Provide at least one field to update.');
  const output = {};
  if (!partial || Object.hasOwn(body, 'title')) {
    if (typeof body.title !== 'string' || body.title.trim().length < 1 || body.title.trim().length > 200) {
      fields.title = 'Title must contain 1 to 200 characters.';
    } else output.title = body.title.trim();
  }
  if (Object.hasOwn(body, 'description')) {
    if (body.description !== null && (typeof body.description !== 'string' || body.description.length > 5000)) {
      fields.description = 'Description must be text up to 5000 characters, or null.';
    } else output.description = body.description;
  }
  if (Object.hasOwn(body, 'dueDate')) {
    if (body.dueDate !== null && !validDate(body.dueDate)) fields.dueDate = 'Due date must be a real YYYY-MM-DD date, or null.';
    else output.dueDate = body.dueDate;
  }
  if (partial && Object.hasOwn(body, 'isCompleted')) {
    if (typeof body.isCompleted !== 'boolean') fields.isCompleted = 'Completion must be a boolean.';
    else output.isCompleted = body.isCompleted;
  }
  if (Object.keys(fields).length) throw new HttpError(400, 'Please correct the invalid fields.', fields);
  return output;
}
