/**
 * @name Hardcoded secret in code
 * @description Finds hardcoded secrets and API keys
 * @kind problem
 * @problem.severity error
 * @id py/hardcoded-secret
 * @tags security
 */

import python

from string value, string name
where
  exists(string s |
    s = "password" or
    s = "secret" or
    s = "token" or
    s = "key" or
    s = "api_key"
  ) and
  (
    // Variable assignment with string literal
    exists(Assignment a |
      a.getTarget().getName() = name and
      name.matches("%" + s + "%") and
      a.getValue().(StrConst).getText() = value and
      value.length() > 10 and
      not value.matches("%localhost%") and
      not value.matches("%example%")
    ) or

    // Function parameter with default value
    exists(Parameter p |
      p.getName().matches("%" + s + "%") and
      p.getDefault().(StrConst).getText() = value and
      value.length() > 10
    )
  )
select value, "Hardcoded secret detected: " + value
