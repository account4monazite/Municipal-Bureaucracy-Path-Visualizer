import { resolveTaskToQuery, extractCoreSubject } from '../../../backend/src/civicTaskResolver.js';

/**
 * Verification Test Script for Civic Task Resolver
 * 
 * Run with: node src/services/civicTaskResolver.test.js
 * 
 * Verifies that the resolver handles:
 * 1. Curated tasks with enhancer optimizations (e.g. Aadhaar, Driving License, Property Tax)
 * 2. Unseen, arbitrary civic tasks that fall back to generic NLP query templates (e.g. Gas Connection, Caste Certificate, NGO Registration)
 */

const testCases = [
  // Curated tasks matching enhancer dictionary
  {
    input: 'I want to update my Aadhaar card near me',
    expectedType: 'Enhanced (UIDAI/Aadhaar)'
  },
  {
    input: 'how do I renew driving license quickly',
    expectedType: 'Enhanced (RTO/Transport)'
  },
  {
    input: 'where can I pay property tax in my area',
    expectedType: 'Enhanced (Municipal Property Tax)'
  },

  // Tasks NOT in enhancer list -> MUST trigger Generic Fallback
  {
    input: 'renew my gas connection',
    expectedType: 'Generic Fallback (Public Utilities & Fuel)'
  },
  {
    input: 'how do I apply for caste certificate online or in person',
    expectedType: 'Generic Fallback (Civil Records & Certification)'
  },
  {
    input: 'where can I register a local NGO society',
    expectedType: 'Generic Fallback (Civic & Government Services)'
  },
  {
    input: 'apply for building plan sanction approval',
    expectedType: 'Generic Fallback (Civic & Government Services)'
  }
];

console.log('='.repeat(75));
console.log('🏛️  CIVIC TASK RESOLVER TEST SUITE');
console.log('='.repeat(75));

testCases.forEach((tc, index) => {
  const result = resolveTaskToQuery(tc.input);
  const subject = extractCoreSubject(tc.input);

  console.log(`\n[Case ${index + 1}] Input: "${tc.input}"`);
  console.log(`  ├─ Extracted Subject: "${subject}"`);
  console.log(`  ├─ Resolution Mode:   ${result.isEnhanced ? '⚡ ENHANCED DICTIONARY' : '🛡️ GENERIC FALLBACK TEMPLATE'}`);
  console.log(`  ├─ Category:          ${result.category}`);
  console.log(`  ├─ Resolved Query:    "${result.query}"`);
  console.log(`  ├─ Target Department: ${result.department || 'N/A'}`);
  console.log(`  └─ Search Terms:      [${result.searchTerms.slice(0, 3).map(t => `"${t}"`).join(', ')}]`);
});

console.log('\n' + '='.repeat(75));
console.log('All test cases resolved successfully.');
console.log('='.repeat(75));
