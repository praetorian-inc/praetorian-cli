# Changelog

## 1.5.1 (2024-10-15)

* [Bug fix] Fixed errors in functions related to principals in
  the Accounts class

## 1.5.0 (2024-10-15)

* [Breaking change] `username`, `password`, `client_id` instance
  attributes of the `Keychain` class are now accessed by functions
  of the same names, ie, `username()`, `password()`, and `client_id()`
* [Breaking change] `api` instance attribute of the `Keychain`
  class is now accessed by the `base_url()` function
* [Breaking change] 'T', 'I', 'R', and 'O' are no longer valid
  statuses for risks

