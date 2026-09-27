/**
 * Civic Task Enhancer Mappings (Indian Municipal & Civic Services)
 * =================================================================
 * 
 * IMPORTANT ARCHITECTURAL NOTE:
 * This configuration is strictly an "accuracy enhancer" dictionary for common
 * administrative acronyms, colloquial terms, and specialized government bodies
 * (e.g., mapping "Aadhaar" -> "Aadhaar Seva Kendra UIDAI", or "driving license" -> "Regional Transport Office RTO").
 * 
 * IT DOES NOT LIMIT SUPPORTED TASKS.
 * The system supports ANY arbitrary civic or government task described in natural language.
 * When a user's task does not match any entry in this enhancer list, civicTaskResolver.js
 * automatically falls back to NLP phrase stripping and general civic query templates
 * (e.g., "{subject} government office", "{subject} seva kendra").
 */

export const taskEnhancers = [
  {
    id: 'aadhaar',
    name: 'Aadhaar Card Services',
    aliases: ['aadhaar', 'uidai', 'biometric update', 'aadhaar card', 'adhar', 'adhaar', 'update aadhaar'],
    category: 'Identity & Biometrics',
    department: 'Unique Identification Authority of India (UIDAI)',
    enhancedQuery: 'Aadhaar Seva Kendra UIDAI center',
    searchTerms: [
      'Aadhaar Seva Kendra',
      'UIDAI Enrollment Center',
      'CSC Aadhaar Center',
      'Bank Aadhaar Seva Kendra'
    ]
  },
  {
    id: 'pan_card',
    name: 'PAN Card Services',
    aliases: ['pan card', 'pan update', 'pan application', 'nsdl pan', 'utiitsl', 'income tax pan'],
    category: 'Taxation & Financial Identity',
    department: 'Income Tax Department / NSDL / UTIITSL',
    enhancedQuery: 'NSDL UTIITSL PAN card facilitation center',
    searchTerms: [
      'TIN Facilitation Center',
      'UTIITSL PAN Office',
      'PAN Card Center',
      'Income Tax Office'
    ]
  },
  {
    id: 'passport',
    name: 'Passport Services',
    aliases: ['passport', 'tatkaal passport', 'passport renewal', 'psk', 'popsk', 'rpo'],
    category: 'Travel & Passports',
    department: 'Ministry of External Affairs (CPV Division)',
    enhancedQuery: 'Passport Seva Kendra PSK',
    searchTerms: [
      'Passport Seva Kendra',
      'Post Office Passport Seva Kendra',
      'Regional Passport Office'
    ]
  },
  {
    id: 'rto_driving_license',
    name: 'Driving License & Vehicle Registration',
    aliases: [
      'driving license',
      'driving licence',
      'driver license',
      'renew driving license',
      'dl renewal',
      'rto',
      'vehicle registration',
      'rc transfer',
      'learner license',
      'commercial license'
    ],
    category: 'Transport & Motor Vehicles',
    department: 'Regional Transport Office (RTO) / Motor Vehicles Dept',
    enhancedQuery: 'Regional Transport Office RTO',
    searchTerms: [
      'Regional Transport Office',
      'RTO Office',
      'Automated Driving Test Center',
      'District Transport Office'
    ]
  },
  {
    id: 'voter_id',
    name: 'Voter ID & Electoral Roll',
    aliases: ['voter id', 'election card', 'epic card', 'voter registration', 'electoral roll', 'voter card'],
    category: 'Electoral Services',
    department: 'Election Commission of India / Chief Electoral Officer',
    enhancedQuery: 'Election Commission Registration Office Voter Seva',
    searchTerms: [
      'Election Office',
      'Voter Facilitation Center',
      'Tehsildar Office Election Branch',
      'District Election Office'
    ]
  },
  {
    id: 'birth_death_cert',
    name: 'Birth & Death Registration',
    aliases: [
      'birth certificate',
      'death certificate',
      'birth registration',
      'death registration',
      'crsorgi',
      'birth and death register'
    ],
    category: 'Civil Registration',
    department: 'Municipal Corporation / Local Registrar of Births & Deaths',
    enhancedQuery: 'Municipal Corporation Registrar Birth and Death office',
    searchTerms: [
      'Municipal Health Department',
      'Registrar Birth and Death',
      'Municipal Ward Office',
      'City Health Center'
    ]
  },
  {
    id: 'property_tax',
    name: 'Property Tax & Khata Transfer',
    aliases: [
      'property tax',
      'house tax',
      'holding tax',
      'khata transfer',
      'patta transfer',
      'mutation of property',
      'property tax payment'
    ],
    category: 'Revenue & Municipal Property',
    department: 'Municipal Corporation Revenue Department',
    enhancedQuery: 'Municipal Corporation Property Tax citizen service center',
    searchTerms: [
      'Property Tax Collection Center',
      'Municipal Revenue Office',
      'Municipal Zonal Office',
      'Civic Center'
    ]
  },
  {
    id: 'trade_license',
    name: 'Trade License & Commercial Establishment',
    aliases: [
      'trade license',
      'trade licence',
      'shop establishment',
      'commercial license',
      'business license',
      'gumasta license',
      'factory license'
    ],
    category: 'Commerce & Urban Administration',
    department: 'Municipal Corporation / Urban Local Body Licensing Branch',
    enhancedQuery: 'Municipal Corporation Trade License Department',
    searchTerms: [
      'Trade License Office',
      'Municipal Ward Office Commercial Cell',
      'Urban Local Body Headquarters',
      'District Industries Centre'
    ]
  },
  {
    id: 'ration_card',
    name: 'Ration Card & Food Supplies',
    aliases: ['ration card', 'ration update', 'food security card', 'pds card', 'ration shop card', 'ration card renewal'],
    category: 'Food & Civil Supplies',
    department: 'Department of Food, Civil Supplies & Consumer Affairs',
    enhancedQuery: 'District Food and Civil Supplies Office Ration center',
    searchTerms: [
      'Food and Civil Supplies Office',
      'Fair Price Shop Office',
      'District Rationing Office',
      'Jan Suvidha Kendra'
    ]
  },
  {
    id: 'water_connection',
    name: 'Water Supply & Sewerage Connection',
    aliases: [
      'water connection',
      'water meter',
      'jal board',
      'water supply',
      'sewerage connection',
      'water bill dispute'
    ],
    category: 'Municipal Utilities',
    department: 'Municipal Water Supply & Sewerage Board / Jal Board',
    enhancedQuery: 'Municipal Water Board Jal Board zonal office',
    searchTerms: [
      'Jal Board Zonal Office',
      'Water Works Department',
      'Municipal Water Supply Office',
      'Public Health Engineering Department'
    ]
  },
  {
    id: 'electricity_connection',
    name: 'Electricity Connection & DISCOM',
    aliases: [
      'electricity connection',
      'power meter',
      'electricity bill',
      'power discom',
      'electric connection',
      'power substation',
      'meter change'
    ],
    category: 'Electricity & Power Utilities',
    department: 'State Electricity Distribution Company (DISCOM)',
    enhancedQuery: 'Electricity Board Substation DISCOM consumer service center',
    searchTerms: [
      'Electricity Board Office',
      'DISCOM Consumer Care Center',
      'Power Substation Office',
      'Bijli Vibhag Office'
    ]
  },
  {
    id: 'senior_citizen_id',
    name: 'Senior Citizen Identity & Welfare',
    aliases: [
      'senior citizen id',
      'senior citizen card',
      'elderly pension',
      'vridha pension',
      'senior citizen welfare'
    ],
    category: 'Social Welfare & Empowerment',
    department: 'District Social Welfare Office',
    enhancedQuery: 'District Social Welfare Office Senior Citizen Seva',
    searchTerms: [
      'District Social Welfare Office',
      'Samaj Kalyan Vibhag',
      'Senior Citizen Facilitation Counter',
      'Jan Seva Kendra'
    ]
  }
];

export default taskEnhancers;
