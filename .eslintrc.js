module.exports = {
  env: {
    browser: true,
    es6: true,
  },
  extends: [
    'airbnb-base',
  ],
  globals: {
    Atomics: 'readonly',
    SharedArrayBuffer: 'readonly',
    log: 'readonly',
    query: 'readonly',
    setMemory: 'readonly',
    getMemory: 'readonly'
  },
  parserOptions: {
    ecmaVersion: 2018,
  },
  rules: {
    "prefer-arrow-callback": "off",
    "prefer-template": "off",
    "no-var": "off",
    "func-names": "off",
    "space-before-function-paren": ["error", {
       "anonymous": "never",
       "named": "never",
       "asyncArrow": "always"
    }],
    "no-unused-vars": "off"
  },
};
