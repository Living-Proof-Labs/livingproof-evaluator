import { readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

import Ajv2020 from "ajv/dist/2020.js"

const here = dirname(fileURLToPath(import.meta.url))
const schemaRoot = resolve(here, "../../schema")
const implementationId =
  "https://github.com/Living-Proof-Labs/livingproof-evaluator/schema/implementation.schema.json"
const resultId =
  "https://github.com/Living-Proof-Labs/livingproof-evaluator/schema/evaluator-result.schema.json"

function schemaFiles(directory, found = []) {
  for (const name of readdirSync(directory)) {
    const path = join(directory, name)
    if (statSync(path).isDirectory()) schemaFiles(path, found)
    else if (name.endsWith(".schema.json")) found.push(path)
  }
  return found
}

const ajv = new Ajv2020({ allErrors: true, strict: false, logger: false })
for (const path of schemaFiles(schemaRoot)) {
  ajv.addSchema(JSON.parse(readFileSync(path, "utf8")))
}

const document = JSON.parse(readFileSync(process.argv[2], "utf8"))
const format = typeof document.format === "string" ? document.format : ""
const schemaId = format.startsWith("livingproof-evaluator-implementation/")
  ? implementationId
  : resultId
if (!ajv.validate(schemaId, document)) process.exit(1)
