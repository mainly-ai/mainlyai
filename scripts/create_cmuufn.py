from mirmod import miranda

sc = miranda.create_security_context(auth_from_config=True)

with sc.connect() as con:
    with con.cursor(dictionary=True) as cur:
        cur.execute("""CREATE FUNCTION CURRENT_MIRANDA_USER_UNPREFIXED() RETURNS CHAR(128)
DETERMINISTIC
BEGIN
  DECLARE miranda_user CHAR(128);
  SELECT role_name INTO miranda_user FROM information_schema.APPLICABLE_ROLES where IS_DEFAULT = 'YES' AND role_name LIKE 'miranda_%' limit 1;
  IF miranda_user IS NULL THEN
    SET miranda_user = USER();
  END IF;
  SET miranda_user = TRIM('`' from REGEXP_REPLACE(miranda_user,'@.*',''));
  RETURN SUBSTRING(miranda_user, 9); -- remove 'miranda_' prefix
END;""")
        con.commit()
