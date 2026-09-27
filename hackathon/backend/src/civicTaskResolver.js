import { taskEnhancers } from '../config/taskMappings.js';

/**
 * Common filler phrases and intent prefixes that users type when
 * describing a government task in natural language.
 */
const INTENT_PREFIXES = [
  // Conversational prompts
  'i want to',
  'i need to',
  'how do i',
  'how can i',
  'how to',
  'where can i',
  'where do i',
  'where should i',
  'where to',
  'where is',
  'can you tell me how to',
  'tell me how to',
  'please help me to',
  'please help me',
  'help me to',
  'help me',
  'looking to',
  'looking for',
  'searching for',
  'trying to',
  'i would like to',
  'we want to',
  'is it possible to',

  // Administrative actions
  'apply for a new',
  'apply for an',
  'apply for a',
  'apply for the',
  'apply for',
  'application for a',
  'application for an',
  'application for',
  'renew my',
  'renew a',
  'renew an',
  'renew the',
  'renew',
  'renewal of my',
  'renewal of a',
  'renewal of',
  'renewal for',
  'register a new',
  'register an',
  'register a',
  'register my',
  'register the',
  'register',
  'registration of a',
  'registration of an',
  'registration of',
  'registration for',
  'update my',
  'update a',
  'update an',
  'update the',
  'update',
  'updation of',
  'get a new',
  'get an',
  'get a',
  'get my',
  'get the',
  'get',
  'obtain a',
  'obtain an',
  'obtain the',
  'obtain',
  'procure a',
  'procure an',
  'procure',
  'pay my',
  'pay for my',
  'pay for a',
  'pay for',
  'pay a',
  'pay the',
  'pay',
  'payment of',
  'payment for',
  'change address in my',
  'change address in',
  'change name in my',
  'change name in',
  'correction in my',
  'correction in',
  'change of',
  'issue of a',
  'issue of an',
  'issue of',
  'issuance of a',
  'issuance of an',
  'issuance of',
];

/**
 * Common location or conversational suffixes
 */
const INTENT_SUFFIXES = [
  'near me please',
  'near me',
  'nearby',
  'near my location',
  'near my area',
  'in my area',
  'close to me',
  'closest to me',
  'closest',
  'around here',
  'around me',
  'locally',
  'online or offline',
  'offline or online',
  'offline',
  'in person',
  'physically',
  'at the center',
  'at the office',
  'urgently',
  'asap',
  'today',
  'process',
  'procedure',
  'guidelines',
  'steps',
  'requirements',
  'in india',
  'in my city',
  'in my town',
];

/**
 * Words to strip from ends of extracted subject
 */
const LEADING_TRAILING_NOISE = new Set([
  'a', 'an', 'the', 'my', 'our', 'for', 'to', 'of', 'in', 'on', 'at', 'with', 'and', 'or', 'new'
]);

/**
 * Extracts the core subject noun phrase from free-form natural language text.
 * Iteratively strips conversational preambles, action verbs, and trailing location qualifiers.
 *
 * Example:
 *  "I want to renew my gas connection near me" -> "gas connection"
 *  "how do I apply for caste certificate online or in person" -> "caste certificate"
 * 
 * @param {string} text Free text civic task description
 * @returns {string} Extracted core subject
 */
export function extractCoreSubject(text) {
  if (!text || typeof text !== 'string') return '';

  let cleaned = text
    .toLowerCase()
    .replace(/[^\w\s-]/g, ' ') // Replace punctuation with space
    .replace(/\s+/g, ' ')      // Normalize whitespace
    .trim();

  if (!cleaned) return '';

  // 1. Iteratively strip intent prefixes (check longest prefixes first)
  const sortedPrefixes = [...INTENT_PREFIXES].sort((a, b) => b.length - a.length);
  let prefixStripped = true;
  while (prefixStripped) {
    prefixStripped = false;
    for (const prefix of sortedPrefixes) {
      if (cleaned === prefix) {
        cleaned = '';
        break;
      }
      if (cleaned.startsWith(prefix + ' ')) {
        cleaned = cleaned.slice(prefix.length).trim();
        prefixStripped = true;
        break;
      }
    }
  }

  // 2. Iteratively strip intent suffixes (check longest suffixes first)
  const sortedSuffixes = [
    ...INTENT_SUFFIXES,
    'in person',
    'online or in person',
    'in person or online',
    'online',
    'quickly',
    'fast'
  ].sort((a, b) => b.length - a.length);

  let suffixStripped = true;
  while (suffixStripped) {
    suffixStripped = false;
    for (const suffix of sortedSuffixes) {
      if (cleaned === suffix) {
        cleaned = '';
        break;
      }
      if (cleaned.endsWith(' ' + suffix)) {
        cleaned = cleaned.slice(0, cleaned.length - suffix.length).trim();
        suffixStripped = true;
        break;
      }
    }
  }

  // 3. Trim leading and trailing noise words (e.g. "a", "an", "the", "my", "for", "or")
  let words = cleaned.split(' ').filter(Boolean);
  while (words.length > 1 && LEADING_TRAILING_NOISE.has(words[0])) {
    words.shift();
  }
  while (words.length > 1 && LEADING_TRAILING_NOISE.has(words[words.length - 1])) {
    words.pop();
  }

  return words.join(' ').trim();
}

/**
 * Lightweight heuristic category classifier for arbitrary civic tasks
 * that fall outside the common enhancer mappings.
 *
 * @param {string} subject Extracted task subject
 * @returns {string} Inferred category name
 */
export function inferCategory(subject) {
  const s = subject.toLowerCase();

  if (/certificate|praman|patra|birth|death|caste|income|domicile|character|disability|marriage/.test(s)) {
    return 'Civil Records & Certification';
  }
  if (/gas|lpg|cylinder|petroleum|fuel|pipe gas|bharat gas|indane|hp gas/.test(s)) {
    return 'Public Utilities & Fuel';
  }
  if (/water|jal|sewer|drainage|tanker/.test(s)) {
    return 'Municipal Water & Sanitation';
  }
  if (/electricity|power|bijli|meter|discom|substation/.test(s)) {
    return 'Electricity & Power Utilities';
  }
  if (/license|licence|permit|rto|driving|vehicle|registration|challan|puc/.test(s)) {
    return 'Transport & Licensing';
  }
  if (/tax|revenue|khata|patta|stamp|registry|sub-registrar|mutation|deed/.test(s)) {
    return 'Revenue & Property Registration';
  }
  if (/pension|ration|bpl|welfare|scholarship|subsidy|samaj kalyan|differently abled/.test(s)) {
    return 'Social Welfare & Public Distribution';
  }
  if (/police|verification|fir|complaint|arms|security|traffic/.test(s)) {
    return 'Law Enforcement & Public Safety';
  }
  if (/health|hospital|dispensary|clinic|vaccination|ayushman/.test(s)) {
    return 'Public Health & Medical Services';
  }
  if (/education|school|college|admission|board|marksheet/.test(s)) {
    return 'Education & Literacy';
  }
  if (/trade|business|shop|gumasta|fssai|company|msme|udyam/.test(s)) {
    return 'Commerce & Business Licensing';
  }

  return 'Civic & Government Services';
}

/**
 * Builds generic fallback search terms and query templates for any civic task.
 * Formulates high-relevance search phrases for Google Maps / Google Places.
 *
 * @param {string} subject Core subject
 * @returns {{ primaryQuery: string, searchTerms: string[] }}
 */
export function buildGenericCivicQuery(subject) {
  if (!subject) {
    return {
      primaryQuery: 'Civic Center Municipal Corporation office',
      searchTerms: [
        'Civic Center',
        'Municipal Corporation Office',
        'Citizen Facilitation Center'
      ]
    };
  }

  const sLower = subject.toLowerCase();

  // If the user already provided specific agency terms (e.g. "gas connection"),
  // optimize the primary search query for realistic physical venues
  let primaryQuery;
  const terms = [];

  if (/gas|lpg|cylinder/.test(sLower)) {
    primaryQuery = `${subject} agency distributor office`;
    terms.push(`${subject} agency distributor office`);
    terms.push(`${subject} customer service center`);
    terms.push(`${subject} booking office`);
    terms.push(`${subject} seva kendra`);
  } else if (/certificate/.test(sLower)) {
    primaryQuery = `${subject} government office`;
    terms.push(`${subject} government office`);
    terms.push(`${subject} Tehsildar Sub-Divisional Magistrate office`);
    terms.push(`${subject} seva kendra`);
    terms.push(`Citizen Facilitation Center for ${subject}`);
  } else if (/\b(office|center|centre|kendra|department|board|bhavan|bhawan)\b/.test(sLower)) {
    primaryQuery = `${subject} government`;
    terms.push(`${subject} government`);
    terms.push(`${subject} citizen service`);
    terms.push(`${subject}`);
  } else {
    primaryQuery = `${subject} government office`;
    terms.push(`${subject} government office`);
    terms.push(`${subject} application center`);
    terms.push(`${subject} seva kendra`);
    terms.push(`${subject} citizen facilitation center`);
  }

  return {
    primaryQuery,
    searchTerms: Array.from(new Set(terms))
  };
}

/**
 * Resolves ANY free-form government task into an actionable Google Places search query.
 * 
 * Works in two steps:
 * 1. Checks the accuracy enhancer dictionary (src/config/taskMappings.js) for
 *    specific administrative acronyms and specialized service centers.
 * 2. If no enhancer matches, automatically extracts the core subject and
 *    constructs a tailored generic search query via robust civic templates.
 *
 * @param {string} taskText Free text entered by user (e.g., "renew my gas connection", "Aadhaar update")
 * @returns {{
 *   query: string,
 *   category: string,
 *   searchTerms: string[],
 *   isEnhanced: boolean,
 *   subject: string,
 *   department?: string
 * }}
 */
export function resolveTaskToQuery(taskText) {
  const rawInput = (taskText || '').trim();
  const subject = extractCoreSubject(rawInput) || rawInput;
  const normalizedTask = rawInput.toLowerCase();
  const normalizedSubject = subject.toLowerCase();

  // Step 1: Check Enhancer Mappings (sorted by alias specificity/length)
  let bestEnhancer = null;
  let maxAliasMatchLength = 0;

  for (const enhancer of taskEnhancers) {
    for (const alias of enhancer.aliases) {
      const aliasLower = alias.toLowerCase();
      // Match either full text or extracted subject
      const regex = new RegExp(`\\b${aliasLower}\\b`, 'i');
      if (regex.test(normalizedTask) || regex.test(normalizedSubject)) {
        if (aliasLower.length > maxAliasMatchLength) {
          maxAliasMatchLength = aliasLower.length;
          bestEnhancer = enhancer;
        }
      }
    }
  }

  // If a curated enhancer matches, return its high-fidelity configuration
  if (bestEnhancer) {
    return {
      query: bestEnhancer.enhancedQuery,
      category: bestEnhancer.category,
      searchTerms: bestEnhancer.searchTerms,
      isEnhanced: true,
      subject: subject || bestEnhancer.name,
      department: bestEnhancer.department,
      enhancerId: bestEnhancer.id
    };
  }

  // Step 2: Generic Fallback Resolution (works for ANY arbitrary civic task)
  const category = inferCategory(subject);
  const { primaryQuery, searchTerms } = buildGenericCivicQuery(subject);

  return {
    query: primaryQuery,
    category,
    searchTerms,
    isEnhanced: false,
    subject: subject || 'Civic Services',
    department: 'Local Municipal / State Government Administrative Office'
  };
}

export default {
  resolveTaskToQuery,
  extractCoreSubject,
  inferCategory,
  buildGenericCivicQuery
};
